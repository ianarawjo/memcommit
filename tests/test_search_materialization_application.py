"""Application and runtime contracts for Search result materialization."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

import memcommit.application.ops as ops
import memcommit.adapters.console.commands.search.command as search_command
import memcommit.application.operations.search.materialization_application as materialization_application
import memcommit.application.operations.search.materialization_runtime as materialization_runtime
import memcommit.persistence.store as store_module
from memcommit.application.authority.access import resolve_context_access
from memcommit.adapters.console.shared.readable_context_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.adapters.console.commands.search.search_workbench import (
    SearchWorkbenchResult,
)
from memcommit.core.context import Memory, MemoryRef
from memcommit.application.operations.search.application import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from memcommit.application.operations.search.materialization_application import (
    SearchMaterializationError,
    SearchMaterializationRequest,
    SearchMaterializationResult,
    FrozenSearchMaterialization,
    run_search_materialization,
)
from memcommit.application.operations.search.materialization_runtime import (
    MemoryStoreSearchMaterializationPort,
    execute_search_materialization,
)
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import create_authority_grant
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)


def _catalog(store: MemoryStore, context_name: str):
    access = resolve_context_access(
        store,
        context_name,
        current_name=context_name,
        required_permission="READ",
    )
    return freeze_readable_context_catalog(store, access)


def _response(source, *memories: Memory) -> SearchResponse:
    return SearchResponse(
        SearchRequest("accessibility", (source.name,)),
        "CURRENT",
        tuple(
            SearchResult(
                context_name=source.name,
                kind="memory",
                uid=memory.uid,
                content=memory.content,
                source_context_name=source.name,
                source_context_uid=source.uid,
                source_memory_uid=memory.uid,
            )
            for memory in memories
        ),
    )


def _request(
    source,
    *memories: Memory,
    indices=(0,),
    mode="COPY",
    destination="results/accessibility",
) -> SearchMaterializationRequest:
    return SearchMaterializationRequest(
        response=_response(source, *memories),
        selected_result_indices=indices,
        mode=mode,
        destination_name=destination,
    )


def test_run_search_materialization_preserves_exact_prepare_publish_contract():
    source = ops.init("source")
    memory = ops.add(source, "Accessible entrance is on the east side.")
    request = _request(source, memory)
    phases = []

    class Port:
        def prepare(self, value):
            phases.append(("prepare", value))
            return FrozenSearchMaterialization(
                mode=value.mode,
                destination_name=value.destination_name,
                source_count=1,
                token="opaque",
            )

        def materialize(self, prepared):
            phases.append(("materialize", prepared))
            return SearchMaterializationResult(
                mode=prepared.mode,
                context_name=prepared.destination_name,
                context_uid="context-result",
                checkpoint_uid="checkpoint-result",
                item_uids=("memory-result",),
            )

    result = run_search_materialization(request, port=Port())

    assert phases[0] == ("prepare", request)
    assert phases[1][0] == "materialize"
    assert result.context_name == request.destination_name
    assert result.item_uids == ("memory-result",)


def test_materialization_request_rejects_nonmemory_and_duplicate_source():
    source = ops.init("source")
    memory = ops.add(source, "Source Memory")
    current = _response(source, memory)
    artifact = SearchResponse(
        current.request,
        "CURRENT",
        (
            SearchResult(
                context_name=source.name,
                kind="artifact",
                uid="artifact-1",
                content="Retained activity",
            ),
        ),
    )
    duplicate = SearchResponse(
        current.request,
        "CURRENT",
        (current.results[0], current.results[0]),
    )

    with pytest.raises(SearchMaterializationError, match="artifact results"):
        SearchMaterializationRequest(artifact, (0,), "COPY", "result")
    with pytest.raises(SearchMaterializationError, match="more than once"):
        SearchMaterializationRequest(duplicate, (0, 1), "COPY", "result")


def test_application_rejects_mismatched_prepared_plan_before_effect():
    source = ops.init("source")
    memory = ops.add(source, "Source Memory")
    materialize_calls = 0

    class Port:
        def prepare(self, _request):
            return FrozenSearchMaterialization(
                mode="COPY",
                destination_name="different-result",
                source_count=1,
                token="opaque",
            )

        def materialize(self, _prepared):
            nonlocal materialize_calls
            materialize_calls += 1
            raise AssertionError("A mismatched plan must not reach publication.")

    with pytest.raises(SearchMaterializationError, match="does not match"):
        run_search_materialization(_request(source, memory), port=Port())

    assert materialize_calls == 0


def test_runtime_materializes_only_selected_copy_without_terminal_or_source_change(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    source = ops.init("task/local/source")
    first = ops.add(source, "First result")
    second = ops.add(source, "Second result")
    store.save(source)
    source_before = context_record_digest(store.load_direct(source.name))

    result = execute_search_materialization(
        _request(
            source,
            first,
            second,
            indices=(1,),
            destination="task/local/results/selected",
        ),
        store=store,
        catalog=_catalog(store, source.name),
    )

    output = tuple(store.load_direct(result.context_name).iter_items())
    assert len(output) == 1
    assert isinstance(output[0], Memory)
    assert output[0].content == second.content
    assert output[0].uid != second.uid
    assert context_record_digest(store.load_direct(source.name)) == source_before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_search_tui_adapter_submits_one_typed_materialization_request(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("task/local/source")
    memory = ops.add(source, "Selected result")
    store.save(source)
    store.set_current(source.name)
    access = resolve_context_access(
        store,
        source.name,
        current_name=source.name,
        required_permission="READ",
    )
    response = _response(source, memory)
    destination = "task/local/results/from-tui"
    observed = []

    monkeypatch.setattr(
        search_command,
        "run_search_workbench",
        lambda *_args, **_kwargs: SearchWorkbenchResult(
            "MATERIALIZE",
            response,
            selected_result_indices=(0,),
            materialize_as="COPY",
            save_location=destination,
        ),
    )

    def execute(request, *, store, catalog):
        observed.append((request, store, catalog))
        return SearchMaterializationResult(
            mode=request.mode,
            context_name=request.destination_name,
            context_uid="result-context",
            checkpoint_uid="result-checkpoint",
            item_uids=("result-memory",),
        )

    monkeypatch.setattr(search_command, "execute_search_materialization", execute)

    search_command._open_search_workbench(
        store,
        access,
        current_name=source.name,
        include_descendants=False,
        follow_embeds=False,
        limit=5,
    )

    assert len(observed) == 1
    request, selected_store, catalog = observed[0]
    assert isinstance(request, SearchMaterializationRequest)
    assert request.response is response
    assert request.selected_result_indices == (0,)
    assert request.mode == "COPY"
    assert request.destination_name == destination
    assert selected_store is store
    assert catalog.access_for(source.name).display_name == source.name


def test_runtime_reference_uses_live_reference_and_leaves_source_unchanged(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("task/local/source")
    memory = ops.add(source, "Source-owned result")
    store.save(source)
    source_before = context_record_digest(store.load_direct(source.name))

    result = execute_search_materialization(
        _request(
            source,
            memory,
            mode="REFERENCE",
            destination="task/local/results/reference",
        ),
        store=store,
        catalog=_catalog(store, source.name),
    )

    item = tuple(store.load_direct(result.context_name).iter_items())[0]
    assert isinstance(item, MemoryRef)
    assert item.target_context_uid == source.uid
    assert item.target_memory_uid == memory.uid
    assert context_record_digest(store.load_direct(source.name)) == source_before


def test_runtime_rechecks_source_between_prepare_and_publication(isolated_store):
    store = MemoryStore()
    source = ops.init("task/local/source")
    memory = ops.add(source, "Original source")
    store.save(source)
    destination = "task/local/results/stale"
    port = MemoryStoreSearchMaterializationPort(
        store,
        _catalog(store, source.name),
    )
    prepared = port.prepare(_request(source, memory, destination=destination))
    current = store.load_direct(source.name)
    current.replace(Memory(uid=memory.uid, content="Concurrent source change"))
    store.save(current, expected_context_digest=current._store_digest)

    with pytest.raises(ConcurrentContextUpdateError, match="source Context changed"):
        port.materialize(prepared)

    assert not store.context_exists(destination)


def test_runtime_require_new_blocks_concurrent_destination_owner(isolated_store):
    store = MemoryStore()
    source = ops.init("task/local/source")
    memory = ops.add(source, "Source result")
    store.save(source)
    destination = "task/local/results/collision"
    port = MemoryStoreSearchMaterializationPort(
        store,
        _catalog(store, source.name),
    )
    prepared = port.prepare(_request(source, memory, destination=destination))
    owner = ops.init(destination)
    owner_memory = ops.add(owner, "Concurrent owner's value")
    store.save(owner)

    with pytest.raises(FileExistsError):
        port.materialize(prepared)

    current_owner = store.load_direct(destination)
    assert tuple(current_owner.memories) == (owner_memory.uid,)


def test_runtime_write_failure_rolls_back_checkpoint_and_partial_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("task/local/source")
    memory = ops.add(source, "Source result")
    store.save(source)
    destination = "task/local/results/write-failure"
    original_write = store_module._write_json_atomic

    def fail_destination_context(path, value):
        if (
            path.name == "context.json"
            and isinstance(value, dict)
            and value.get("name") == destination
        ):
            raise OSError("injected destination write failure")
        return original_write(path, value)

    monkeypatch.setattr(store_module, "_write_json_atomic", fail_destination_context)

    with pytest.raises(OSError, match="injected destination write failure"):
        execute_search_materialization(
            _request(source, memory, destination=destination),
            store=store,
            catalog=_catalog(store, source.name),
        )

    assert not store.context_exists(destination)
    assert not store._context_file(destination).exists()
    assert not store._checkpoints_dir(destination).exists()


def _granted_copy_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    active_store = MemoryStore()
    attachment = ops.init("task-root")
    active_store.save(attachment)
    active_store.set_current(attachment.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="search-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    memory = ops.add(source, "Export-authorized granted result")
    authority_store.save(source)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n", encoding="utf-8")
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source.name,
        attachment_name=attachment.name,
        public_name="shared/source",
        permissions=("READ", "DERIVE", "EXPORT", "SAVE_ANALYSIS"),
    )
    access = resolve_context_access(
        active_store,
        "shared/source",
        current_name=attachment.name,
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(active_store, access)
    response = SearchResponse(
        SearchRequest("export result", ("shared/source",)),
        "CURRENT",
        (
            SearchResult(
                context_name="shared/source",
                kind="memory",
                uid=memory.uid,
                content=memory.content,
                source_context_name="shared/source",
                source_context_uid=source.uid,
                source_memory_uid=memory.uid,
            ),
        ),
    )
    return active_store, authority_store, source, memory, catalog, response


def test_granted_copy_revalidates_export_and_reference_stays_local_only(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority_store, source, memory, catalog, response = _granted_copy_fixture(
        tmp_path, monkeypatch
    )
    source_before = context_record_digest(authority_store.load_direct(source.name))
    copy_destination = "task-root/results/granted-copy"

    result = execute_search_materialization(
        SearchMaterializationRequest(
            response,
            (0,),
            "COPY",
            copy_destination,
        ),
        store=store,
        catalog=catalog,
    )

    copied = tuple(store.load_direct(result.context_name).iter_items())[0]
    assert isinstance(copied, Memory)
    assert copied.content == memory.content
    assert context_record_digest(authority_store.load_direct(source.name)) == (
        source_before
    )

    reference_destination = "task-root/results/granted-reference"
    with pytest.raises(SearchMaterializationError, match="locally owned"):
        execute_search_materialization(
            SearchMaterializationRequest(
                response,
                (0,),
                "REFERENCE",
                reference_destination,
            ),
            store=store,
            catalog=catalog,
        )
    assert not store.context_exists(reference_destination)


def test_materialization_application_has_no_command_typer_tui_or_provider_imports():
    for module in (materialization_application, materialization_runtime):
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.append(node.module)

        forbidden = tuple(
            name
            for name in imported
            if name == "typer"
            or name.startswith("prompt_toolkit")
            or name.startswith("memcommit.adapters.console.commands")
            or "provider" in name
        )
        assert forbidden == ()
