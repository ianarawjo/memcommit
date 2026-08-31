"""Shared selected-Memory Context-save contracts and Search adaptation."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

import memcommit.adapters.console.commands.search_explain.retrieve_answer.search.command as search_command
import memcommit.application.capabilities.ops as ops
import memcommit.application.capabilities.save_context_from_selection.application as save_application
import memcommit.application.capabilities.save_context_from_selection.runtime as save_runtime
import memcommit.persistence.store as store_module
from memcommit.adapters.console.commands.search_explain.retrieve_answer.search.search_workbench import (
    SearchWorkbenchResult,
)
from memcommit.application.authorization import ContextUse
from memcommit.application.capabilities.authority.context_access import (
    resolve_context_access,
)
from memcommit.application.capabilities.authority.readable_contexts import (
    freeze_readable_context_catalog,
)
from memcommit.application.capabilities.save_context_from_selection.application import (
    FrozenContextSelectionSave,
    SaveContextFromSelectionError,
    SaveContextFromSelectionRequest,
    SaveContextFromSelectionResult,
    SelectedMemory,
    SelectionOrigin,
    save_context_from_selection,
)
from memcommit.application.capabilities.save_context_from_selection.runtime import (
    MemoryStoreSaveContextFromSelectionPort,
    execute_save_context_from_selection,
)
from memcommit.application.operations.profiles.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profiles.profile.model import create_authority_grant
from memcommit.application.operations.search_explain.retrieve_answer.search.application import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from memcommit.application.operations.search_explain.retrieve_answer.search.save_context import (
    save_context_request_from_search,
)
from memcommit.core.context import Memory, MemoryRef
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


def test_application_preserves_exact_prepare_save_contract():
    request = SaveContextFromSelectionRequest(
        selection=(
            SelectedMemory(
                position=1,
                source_kind="memory",
                source_context_name="source",
                source_context_uid="context-source",
                source_memory_uid="memory-source",
                content="Source Memory",
            ),
        ),
        mode="COPY",
        destination_name="result",
        origin=SelectionOrigin("search", (("query", "source"),)),
    )
    phases = []

    class Port:
        def prepare(self, value):
            phases.append(("prepare", value))
            return FrozenContextSelectionSave(
                mode=value.mode,
                destination_name=value.destination_name,
                source_count=1,
                token="opaque",
            )

        def save(self, prepared):
            phases.append(("save", prepared))
            return SaveContextFromSelectionResult(
                mode=prepared.mode,
                context_name=prepared.destination_name,
                context_uid="context-result",
                checkpoint_uid="checkpoint-result",
                item_uids=("memory-result",),
            )

    result = save_context_from_selection(request, port=Port())

    assert phases[0] == ("prepare", request)
    assert phases[1][0] == "save"
    assert result.context_name == request.destination_name


def test_search_adapter_rejects_nonmemory_and_duplicate_source(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "Source Memory")
    store.save(source)
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
    catalog = _catalog(store, source.name)

    with pytest.raises(SaveContextFromSelectionError, match="artifact results"):
        save_context_request_from_search(
            artifact,
            (0,),
            mode="COPY",
            destination_name="result",
            catalog=catalog,
        )
    with pytest.raises(SaveContextFromSelectionError, match="more than once"):
        save_context_request_from_search(
            duplicate,
            (0, 1),
            mode="COPY",
            destination_name="result",
            catalog=catalog,
        )


@pytest.mark.parametrize("mode", ("COPY", "REFERENCE", "EMBED"))
def test_runtime_saves_each_exact_relationship_mode(isolated_store, mode):
    store = MemoryStore()
    source = ops.init("task/local/source")
    memory = ops.add(source, "Accessible entrance is on the east side.")
    store.save(source)
    source_before = context_record_digest(store.load_direct(source.name))
    catalog = _catalog(store, source.name)

    result = execute_save_context_from_selection(
        save_context_request_from_search(
            _response(source, memory),
            (0,),
            mode=mode,
            destination_name=f"task/local/results/{mode.lower()}",
            catalog=catalog,
        ),
        store=store,
        catalog=catalog,
    )

    item = tuple(store.load_direct(result.context_name).iter_items())[0]
    if mode == "COPY":
        assert isinstance(item, Memory)
        assert item.uid != memory.uid
    else:
        assert isinstance(item, MemoryRef)
        assert item.is_snapshot is (mode == "REFERENCE")
        assert item.is_live is (mode == "EMBED")
        assert item.target_context_uid == source.uid
        assert item.target_memory_uid == memory.uid
    assert item.content == memory.content if isinstance(item, Memory) else True
    assert context_record_digest(store.load_direct(source.name)) == source_before
    checkpoint = store.list_checkpoints(result.context_name)[0]
    saved = checkpoint["args"]["save_context_from_selection"]
    assert saved["mode"] == mode
    assert saved["source_operation"] == "search"
    assert saved["source_arguments"] == {"query": "accessibility"}


def test_reference_is_frozen_while_embed_follows_source(isolated_store):
    store = MemoryStore()
    source = ops.init("task/source")
    memory = ops.add(source, "Before")
    store.save(source)
    catalog = _catalog(store, source.name)
    response = _response(source, memory)

    for mode in ("REFERENCE", "EMBED"):
        execute_save_context_from_selection(
            save_context_request_from_search(
                response,
                (0,),
                mode=mode,
                destination_name=f"task/{mode.lower()}",
                catalog=catalog,
            ),
            store=store,
            catalog=catalog,
        )

    changed = store.load_direct(source.name)
    changed.replace(Memory(uid=memory.uid, content="After"))
    store.save(changed, expected_context_digest=changed._store_digest)

    reference = tuple(store.load("task/reference").iter_items())[0]
    embed = tuple(store.load("task/embed").iter_items())[0]
    assert isinstance(reference, MemoryRef) and reference.target is not None
    assert isinstance(embed, MemoryRef) and embed.target is not None
    assert reference.target.content == "Before"
    assert embed.target.content == "After"


def test_runtime_calls_context_use_authorization_before_saving(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("task/source")
    memory = ops.add(source, "Source")
    store.save(source)
    catalog = _catalog(store, source.name)
    observed = []
    original = save_runtime.authorize_context_use

    def authorize(access, use):
        observed.append((access.display_name, use))
        return original(access, use)

    monkeypatch.setattr(save_runtime, "authorize_context_use", authorize)
    execute_save_context_from_selection(
        save_context_request_from_search(
            _response(source, memory),
            (0,),
            mode="COPY",
            destination_name="task/result",
            catalog=catalog,
        ),
        store=store,
        catalog=catalog,
    )

    assert observed
    assert set(observed) == {(source.name, ContextUse.READ)}


def test_runtime_rechecks_source_between_prepare_and_save(isolated_store):
    store = MemoryStore()
    source = ops.init("task/source")
    memory = ops.add(source, "Original source")
    store.save(source)
    catalog = _catalog(store, source.name)
    port = MemoryStoreSaveContextFromSelectionPort(store, catalog)
    prepared = port.prepare(
        save_context_request_from_search(
            _response(source, memory),
            (0,),
            mode="COPY",
            destination_name="task/stale",
            catalog=catalog,
        )
    )
    current = store.load_direct(source.name)
    current.replace(Memory(uid=memory.uid, content="Concurrent source change"))
    store.save(current, expected_context_digest=current._store_digest)

    with pytest.raises(ConcurrentContextUpdateError, match="source Context changed"):
        port.save(prepared)
    assert not store.context_exists("task/stale")


def test_runtime_require_new_blocks_concurrent_destination_owner(isolated_store):
    store = MemoryStore()
    source = ops.init("task/source")
    memory = ops.add(source, "Source result")
    store.save(source)
    catalog = _catalog(store, source.name)
    port = MemoryStoreSaveContextFromSelectionPort(store, catalog)
    prepared = port.prepare(
        save_context_request_from_search(
            _response(source, memory),
            (0,),
            mode="COPY",
            destination_name="task/collision",
            catalog=catalog,
        )
    )
    owner = ops.init("task/collision")
    owner_memory = ops.add(owner, "Concurrent owner's value")
    store.save(owner)

    with pytest.raises(FileExistsError):
        port.save(prepared)
    assert tuple(store.load_direct(owner.name).memories) == (owner_memory.uid,)


def test_runtime_write_failure_rolls_back_checkpoint_and_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("task/source")
    memory = ops.add(source, "Source result")
    store.save(source)
    catalog = _catalog(store, source.name)
    destination = "task/write-failure"
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
        execute_save_context_from_selection(
            save_context_request_from_search(
                _response(source, memory),
                (0,),
                mode="COPY",
                destination_name=destination,
                catalog=catalog,
            ),
            store=store,
            catalog=catalog,
        )
    assert not store.context_exists(destination)
    assert not store._context_file(destination).exists()
    assert not store._checkpoints_dir(destination).exists()


def _granted_fixture(tmp_path, monkeypatch):
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
    memory = ops.add(source, "READ-authorized granted result")
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
        permissions=("READ",),
    )
    access = resolve_context_access(
        active_store,
        "shared/source",
        current_name=attachment.name,
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(active_store, access)
    response = SearchResponse(
        SearchRequest("granted result", ("shared/source",)),
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


@pytest.mark.parametrize("mode", ("COPY", "REFERENCE", "EMBED"))
def test_read_granted_source_supports_all_save_modes(
    isolated_store,
    tmp_path,
    monkeypatch,
    mode,
):
    store, authority_store, source, memory, catalog, response = _granted_fixture(
        tmp_path,
        monkeypatch,
    )
    source_before = context_record_digest(authority_store.load_direct(source.name))
    destination = f"task-root/results/granted-{mode.lower()}"

    result = execute_save_context_from_selection(
        save_context_request_from_search(
            response,
            (0,),
            mode=mode,
            destination_name=destination,
            catalog=catalog,
        ),
        store=store,
        catalog=catalog,
    )

    item = tuple(store.load_direct(result.context_name).iter_items())[0]
    if mode == "COPY":
        assert isinstance(item, Memory)
    else:
        assert isinstance(item, MemoryRef)
        assert item.is_granted
        assert item.is_snapshot is (mode == "REFERENCE")
        assert item.is_live is (mode == "EMBED")
        resolved = tuple(store.load(result.context_name).iter_items())[0]
        assert isinstance(resolved, MemoryRef) and resolved.target is not None
        assert resolved.target.content == memory.content
    assert context_record_digest(authority_store.load_direct(source.name)) == source_before


def test_search_tui_submits_one_shared_save_request(isolated_store, monkeypatch):
    store = MemoryStore()
    source = ops.init("task/source")
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
    destination = "task/results/from-tui"
    observed = []
    monkeypatch.setattr(
        search_command,
        "run_search_workbench",
        lambda *_args, **_kwargs: SearchWorkbenchResult(
            "SAVE",
            response,
            selected_result_indices=(0,),
            save_as="REFERENCE",
            save_location=destination,
        ),
    )

    def execute(request, *, store, catalog):
        observed.append((request, store, catalog))
        return SaveContextFromSelectionResult(
            mode=request.mode,
            context_name=request.destination_name,
            context_uid="result-context",
            checkpoint_uid="result-checkpoint",
            item_uids=("result-memory",),
        )

    monkeypatch.setattr(search_command, "execute_save_context_from_selection", execute)
    search_command._open_search_workbench(
        store,
        access,
        current_name=source.name,
        include_descendants=False,
        follow_embeds=False,
        limit=5,
    )

    request, selected_store, catalog = observed[0]
    assert isinstance(request, SaveContextFromSelectionRequest)
    assert request.mode == "REFERENCE"
    assert request.destination_name == destination
    assert request.selection[0].source_memory_uid == memory.uid
    assert selected_store is store
    assert catalog.access_for(source.name).display_name == source.name


def test_shared_save_modules_have_no_command_tui_or_provider_imports():
    for module in (save_application, save_runtime):
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
