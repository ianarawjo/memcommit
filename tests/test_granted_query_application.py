"""Read-versus-publication contracts for terminal-independent granted Query."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

import memcommit.ops as ops
from memcommit.context import Memory
from memcommit.commands.query_execution import run_granted_query_request
from memcommit.operations.query.granted_application import (
    GrantedQueryReadOutcome,
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQuerySessionPublication,
    GrantedQuerySessionPublicationResult,
    GrantedQueryTarget,
    PreparedGrantedQuery,
    publish_granted_query_session,
    run_granted_query_read,
)
from memcommit.operations.query.granted_runtime import (
    execute_granted_query_read,
    execute_granted_query_session_publication,
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
from memcommit.query_sessions import QuerySessionError
from memcommit.store import MemoryStore


SECRET = "The north utility tunnel opens only after 18:00."


def _request(*, session_name: str | None = None) -> GrantedQueryRequest:
    return GrantedQueryRequest(
        GrantedQueryTarget(
            grant_uid="grant-1",
            public_name="construction-details",
            attachment_name="task-root",
            session_log_allowed=session_name is not None,
        ),
        "When does it open?",
        session_name=session_name,
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
    source_memory = ops.add(source_context, SECRET)
    authority_store.save(source_context)
    authority_store.set_current(source_context.name)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    _updated, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source_context.name,
        attachment_name=task_context.name,
        public_name="construction-details",
        permissions=("QUERY", "SESSION_LOG"),
    )
    request = GrantedQueryRequest(
        GrantedQueryTarget(
            grant_uid=grant.uid,
            public_name=grant.public_name,
            attachment_name=grant.attachment_context_name,
            session_log_allowed=True,
        ),
        "When does it open?",
        session_name="campus-review",
    )
    return task_store, authority_store, source_context, source_memory, grant, request


class _Provider:
    def query(self, source_name, source_content, question):
        assert source_name == "construction-details"
        assert source_content == SECRET
        assert question == "When does it open?"
        return "After 18:00."


def test_application_returns_unpublished_turn_until_explicit_publication():
    request = _request(session_name="campus-review")
    events: list[str] = []
    token = object()

    class ReadPort:
        def prepare(self, value):
            events.append("prepare")
            return PreparedGrantedQuery(value, token)

        def read(self, prepared, provider, observer=None):
            assert prepared == PreparedGrantedQuery(request, token)
            assert provider is provider_instance
            events.append("read")
            if observer is not None:
                observer("ANSWERING")
                observer("REVALIDATING")
            response = GrantedQueryResponse(request, answer="After 18:00.")
            return GrantedQueryReadOutcome(
                response,
                GrantedQuerySessionPublication(request, response.answer, token),
            )

    class PublicationPort:
        calls = 0

        def publish(self, publication):
            self.calls += 1
            assert publication.token is token
            return GrantedQuerySessionPublicationResult(
                session_name="campus-review",
                revision=1,
                turn_count=1,
            )

    provider_instance = object()

    def provider_factory():
        events.append("provider")
        return provider_instance

    stages: list[str] = []
    publication_port = PublicationPort()
    outcome = run_granted_query_read(
        request,
        read_port=ReadPort(),
        provider_factory=provider_factory,
        observer=stages.append,
    )

    assert events == ["prepare", "provider", "read"]
    assert stages == [
        "AUTHORITY_FROZEN",
        "CONNECTING_PROVIDER",
        "ANSWERING",
        "REVALIDATING",
    ]
    assert outcome.response.answer == "After 18:00."
    assert outcome.publication is not None
    assert publication_port.calls == 0

    receipt = publish_granted_query_session(
        outcome.publication,
        publication_port=publication_port,
        observer=stages.append,
    )

    assert receipt.revision == 1
    assert publication_port.calls == 1
    assert stages[-1] == "PUBLISHING_SESSION"


def test_store_read_returns_publication_plan_without_creating_session_storage(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    task_store, *_rest, request = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    outcome = execute_granted_query_read(
        request,
        store=task_store,
        provider_factory=_Provider,
    )

    assert outcome.response.answer == "After 18:00."
    assert outcome.publication is not None
    assert not (isolated_store / "query-sessions").exists()

    tampered = GrantedQuerySessionPublication(
        request,
        "A substituted answer.",
        outcome.publication.token,
    )
    with pytest.raises(ValueError, match="token is invalid"):
        execute_granted_query_session_publication(tampered, store=task_store)
    assert not (isolated_store / "query-sessions").exists()

    receipt = execute_granted_query_session_publication(
        outcome.publication,
        store=task_store,
    )

    assert receipt == GrantedQuerySessionPublicationResult(
        session_name="campus-review",
        revision=1,
        turn_count=1,
    )
    records = list((isolated_store / "query-sessions").glob("*.json"))
    assert len(records) == 1
    saved = json.loads(records[0].read_text(encoding="utf-8"))
    assert saved["turns"] == [
        {"question": "When does it open?", "answer": "After 18:00."}
    ]
    assert SECRET not in records[0].read_text(encoding="utf-8")

    with pytest.raises(QuerySessionError, match="changed while the provider"):
        execute_granted_query_session_publication(
            outcome.publication,
            store=task_store,
        )
    assert json.loads(records[0].read_text(encoding="utf-8"))["revision"] == 1


def test_compatibility_entry_point_preserves_progress_and_publishes(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    task_store, *_rest, request = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    stages: list[tuple[str, int]] = []

    response = run_granted_query_request(
        task_store,
        request,
        connect_provider=_Provider,
        on_stage=lambda label, step: stages.append((label, step)),
    )

    assert response.answer == "After 18:00."
    assert stages == [
        ("connecting provider", 1),
        ("preparing authorized sources", 2),
        ("answering query", 3),
    ]
    assert len(list((isolated_store / "query-sessions").glob("*.json"))) == 1


def test_revocation_between_read_and_publication_prevents_session_write(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    task_store, _authority, _context, _memory, grant, request = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    outcome = execute_granted_query_read(
        request,
        store=task_store,
        provider_factory=_Provider,
    )
    assert outcome.publication is not None

    delete_authority_grant(grant.uid)

    with pytest.raises(ProfileError, match="does not exist"):
        execute_granted_query_session_publication(
            outcome.publication,
            store=task_store,
        )
    assert not (isolated_store / "query-sessions").exists()


def test_source_change_between_read_and_publication_prevents_session_write(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    task_store, authority_store, context, memory, _grant, request = _authority_grant(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    outcome = execute_granted_query_read(
        request,
        store=task_store,
        provider_factory=_Provider,
    )
    assert outcome.publication is not None

    changed = authority_store.load_direct(context.name)
    assert isinstance(changed.memories[memory.uid], Memory)
    changed.memories[memory.uid].content = "The authority Source changed."
    authority_store.save(changed)

    with pytest.raises(ValueError, match="changed before the turn was saved"):
        execute_granted_query_session_publication(
            outcome.publication,
            store=task_store,
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
        root / "memcommit/operations/query/granted_application.py"
    )
    runtime_imports = imports(root / "memcommit/operations/query/granted_runtime.py")
    forbidden = ("typer", "prompt_toolkit", "memcommit.commands")

    assert not any(name.startswith(forbidden) for name in application_imports)
    assert not any(name.startswith(forbidden) for name in runtime_imports)
    assert "memcommit.store" not in application_imports
    assert "memcommit.query_provider" not in application_imports
    assert "memcommit.query_provider" not in runtime_imports


def test_production_adapters_import_granted_query_from_new_owners():
    root = Path(__file__).parents[1]
    command = (root / "memcommit/commands/query.py").read_text(encoding="utf-8")
    workbench = (root / "memcommit/commands/query_workbench.py").read_text(
        encoding="utf-8"
    )

    assert "from memcommit.operations.query.granted_application import (" in command
    assert "from memcommit.operations.query.granted_runtime import (" in command
    assert "from memcommit.operations.query.granted_application import (" in workbench
