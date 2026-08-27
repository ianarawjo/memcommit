"""Terminal-independent one-shot granted Query contracts."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

import memcommit.application.ops as ops
from memcommit.application.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQueryTarget,
    PreparedGrantedQuery,
    run_granted_query_read,
)
from memcommit.application.operations.query.granted_runtime import (
    execute_granted_query_read,
    execute_granted_query_request,
)
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import (
    ProfileError,
    create_authority_grant,
    delete_authority_grant,
)
from memcommit.store import MemoryStore


SECRET = "The north utility tunnel opens only after 18:00."


def _request() -> GrantedQueryRequest:
    return GrantedQueryRequest(
        GrantedQueryTarget(
            grant_uid="grant-1",
            public_name="construction-details",
            attachment_name="task-root",
        ),
        "When does it open?",
    )


def _authority_grant(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    task_store = MemoryStore()
    task_context = ops.init("task-root")
    task_store.save(task_context)
    task_store.set_current(task_context.name)
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="task-1-campus-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source_context = ops.init("construction-details")
    ops.add(source_context, SECRET)
    authority_store.save(source_context)
    authority_store.set_current(source_context.name)
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n", encoding="utf-8")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source_context.name,
        attachment_name=task_context.name,
        public_name="construction-details",
        permissions=("QUERY",),
    )
    request = GrantedQueryRequest(
        GrantedQueryTarget(
            grant_uid=grant.uid,
            public_name=grant.public_name,
            attachment_name=grant.attachment_context_name,
        ),
        "When does it open?",
    )
    return task_store, grant, request


class _Provider:
    def query(self, source_name, source_content, question):
        assert source_name == "construction-details"
        assert source_content == SECRET
        assert question == "When does it open?"
        return "After 18:00."


def test_application_returns_one_response_without_a_publication_phase():
    request = _request()
    events: list[str] = []
    token = object()
    provider = object()

    class ReadPort:
        def prepare(self, value):
            events.append("prepare")
            return PreparedGrantedQuery(value, token)

        def read(self, prepared, actual_provider, observer=None):
            assert prepared == PreparedGrantedQuery(request, token)
            assert actual_provider is provider
            events.append("read")
            if observer is not None:
                observer("ANSWERING")
                observer("REVALIDATING")
            return GrantedQueryResponse(request, answer="After 18:00.")

    stages: list[str] = []
    response = run_granted_query_read(
        request,
        read_port=ReadPort(),
        provider_factory=lambda: provider,
        observer=stages.append,
    )

    assert response.answer == "After 18:00."
    assert events == ["prepare", "read"]
    assert stages == [
        "AUTHORITY_FROZEN",
        "CONNECTING_PROVIDER",
        "ANSWERING",
        "REVALIDATING",
    ]
    assert not hasattr(response, "publication")


def test_store_runtime_reports_stages_and_never_creates_session_storage(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    task_store, _grant, request = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    stages: list[str] = []
    response = execute_granted_query_request(
        request,
        store=task_store,
        provider_factory=_Provider,
        observer=stages.append,
    )

    assert response.answer == "After 18:00."
    assert stages == [
        "AUTHORITY_FROZEN",
        "CONNECTING_PROVIDER",
        "PREPARING_SOURCES",
        "ANSWERING",
        "REVALIDATING",
    ]
    assert not (isolated_store / "query-sessions").exists()


def test_revocation_during_read_prevents_one_shot_answer_disclosure(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    task_store, grant, request = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def query(self, *_args):
            delete_authority_grant(grant.uid)
            return "must not be disclosed"

    with pytest.raises(
        (FileNotFoundError, ProfileError, ValueError),
        match="does not exist|available",
    ):
        execute_granted_query_read(
            request,
            store=task_store,
            provider_factory=Provider,
        )
    assert not (isolated_store / "query-sessions").exists()


def test_granted_query_application_and_runtime_have_no_interface_dependency():
    root = Path(__file__).parents[1]

    def imports(path: Path) -> tuple[str, ...]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        values: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                values.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                values.append(node.module)
        return tuple(values)

    application_imports = imports(
        root / "src/memcommit/application/operations/query/granted_application.py"
    )
    runtime_imports = imports(root / "src/memcommit/application/operations/query/granted_runtime.py")
    forbidden = ("typer", "prompt_toolkit", "memcommit.commands")

    assert not any(name.startswith(forbidden) for name in application_imports)
    assert not any(name.startswith(forbidden) for name in runtime_imports)
    assert "memcommit.store" not in application_imports
    assert "memcommit.query_provider" not in application_imports
    assert "memcommit.query_provider" not in runtime_imports


def test_production_adapters_import_granted_query_from_operation_owners():
    root = Path(__file__).parents[1]
    command = (root / "src/memcommit/commands/query/command.py").read_text(encoding="utf-8")
    workbench_model = (
        root / "src/memcommit/adapters/interfaces/tui/operations/query/model.py"
    ).read_text(encoding="utf-8")

    assert "from memcommit.application.operations.query.granted_application import (" in command
    assert "from memcommit.application.operations.query.granted_runtime import (" in command
    assert (
        "from memcommit.application.operations.query.granted_application import ("
        in workbench_model
    )
