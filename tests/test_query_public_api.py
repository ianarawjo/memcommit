"""Stable public Python API contracts over the three Query lifecycles."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

import memcommit
import memcommit.ops as ops
from memcommit.api import (
    MemCommitClient,
    OrdinaryQueryResult,
    QueryAuthorityError,
    QueryConfigurationError,
    QueryContextError,
    QueryInputError,
    QueryProviderConfig,
    QueryProviderFailure,
    ReferenceQueryResult,
)
from memcommit.context import QueryContextRef
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import create_authority_grant
from memcommit.store import MemoryStore


class _OrdinaryProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "ordinary query"
        payload = json.loads(prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
        aliases = [item["alias"] for item in payload["complete_frozen_corpus"]]
        return json.dumps(
            {
                "outcome_kind": "ANSWER",
                "blocks": [
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "The root fact is supported.",
                        "source_aliases": aliases,
                    }
                ],
            }
        )


class _GrantedProvider:
    def query(self, source_name, source_content, question):
        assert source_name == "construction-details"
        assert source_content == "The north tunnel opens after 18:00."
        assert question == "When does it open?"
        return "After 18:00."


def _authority_grant(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    task_store = MemoryStore()
    task_context = ops.init("task-root")
    task_store.save(task_context)
    task_store.set_current(task_context.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="campus-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source_context = ops.init("construction-details")
    ops.add(source_context, "The north tunnel opens after 18:00.")
    authority_store.save(source_context)
    authority_store.set_current(source_context.name)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source_context.name,
        attachment_name=task_context.name,
        public_name="construction-details",
        permissions=("QUERY",),
    )
    return task_store


def test_root_package_exports_the_same_public_api_objects():
    assert memcommit.MemCommitClient is MemCommitClient
    assert memcommit.QueryProviderConfig is QueryProviderConfig
    assert memcommit.OrdinaryQueryResult is OrdinaryQueryResult


def test_client_freezes_explicit_root_without_creating_store(tmp_path):
    root = tmp_path / "missing-store"

    client = MemCommitClient(root=root)

    assert client.store_root == root.resolve()
    assert client.profile_name is None
    assert client.query_config == QueryProviderConfig()
    assert not root.exists()


def test_client_rejects_ambiguous_store_ownership(tmp_path):
    with pytest.raises(QueryConfigurationError, match="either"):
        MemCommitClient(root=tmp_path / "store", profile="authoring")


def test_ordinary_query_returns_typed_citations_without_mutating_sources(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("notes")
    memory = ops.add(context, "Root-only fact.")
    store.save(context)
    store.set_current(context.name)
    before = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    }
    stages: list[str] = []
    client = MemCommitClient(
        root=isolated_store,
        ordinary_provider_factory=_OrdinaryProvider,
    )

    result = client.query_ordinary(
        "What is supported?",
        context_names=("notes",),
        include_descendants=False,
        follow_embeds=False,
        on_stage=stages.append,
    )

    assert result.grounded is True
    assert "The root fact is supported. [1]" in result.answer
    assert len(result.citations) == 1
    assert result.citations[0].context_name == "notes"
    assert result.citations[0].uid == memory.uid
    assert result.citations[0].content == "Root-only fact."
    assert stages == ["INPUTS_FROZEN", "CONNECTING_PROVIDER", "ANSWERING"]
    assert {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    } == before


def test_ordinary_query_resolves_all_relative_names_from_one_current_snapshot(
    isolated_store,
):
    store = MemoryStore()
    parent = ops.init("task")
    child = ops.init("task/child")
    ops.add(parent, "Parent fact.")
    ops.add(child, "Child fact.")
    store.save(parent)
    store.save(child)
    store.set_current(child.name)
    client = MemCommitClient(
        root=isolated_store,
        ordinary_provider_factory=_OrdinaryProvider,
    )

    result = client.query_ordinary(
        "What is supported?",
        context_names=(".", ".."),
        follow_embeds=False,
    )

    assert result.grounded is True
    assert {citation.context_name for citation in result.citations} == {
        "task",
        "task/child",
    }


def test_reference_query_authenticates_before_opening_and_never_publishes(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = store.create_query_source(
        "construction-details",
        "The rear entrance closes at 17:00.",
    )
    events: list[str] = []

    class Provider:
        def query(self, source_name, source_content, question):
            events.append("answer")
            assert source_name == "construction-details"
            assert source_content == "The rear entrance closes at 17:00."
            assert question == "What closes?"
            return "The rear entrance closes."

    def provider_factory(provider_name):
        events.append("provider")
        assert provider_name == "codex_chatgpt"
        return Provider()

    client = MemCommitClient(
        root=isolated_store,
        query_route_provider_factory=provider_factory,
    )
    original_open = client._store.load_query_source

    def open_source(*args, **kwargs):
        events.append("source")
        return original_open(*args, **kwargs)

    monkeypatch.setattr(client._store, "load_query_source", open_source)
    before = tuple(
        sorted(path.relative_to(isolated_store) for path in isolated_store.rglob("*"))
    )

    result = client.query_reference(
        QueryContextRef(
            uid="route-1",
            name="construction-details",
            target_source_uid=source.uid,
            provider="codex_chatgpt",
        ),
        "What closes?",
    )

    assert result == ReferenceQueryResult(
        source_name="construction-details",
        answer="The rear entrance closes.",
    )
    assert events == ["provider", "source", "answer"]
    assert (
        tuple(
            sorted(
                path.relative_to(isolated_store) for path in isolated_store.rglob("*")
            )
        )
        == before
    )


def test_granted_query_high_level_success_is_process_local(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(isolated_store, tmp_path, monkeypatch)
    stages: list[str] = []
    client = MemCommitClient(ordinary_provider_factory=_GrantedProvider)

    result = client.query_granted(
        "construction-details",
        "When does it open?",
        federate_descendants=False,
        on_stage=stages.append,
    )

    assert result.public_name == "construction-details"
    assert result.answer == "After 18:00."
    assert stages == [
        "AUTHORITY_FROZEN",
        "CONNECTING_PROVIDER",
        "PREPARING_SOURCES",
        "ANSWERING",
        "REVALIDATING",
    ]
    assert not (isolated_store / "query-sessions").exists()


def test_explicit_root_never_inherits_host_granted_query(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_grant(isolated_store, tmp_path, monkeypatch)
    provider_called = False

    def provider_factory():
        nonlocal provider_called
        provider_called = True
        return _GrantedProvider()

    client = MemCommitClient(
        root=isolated_store,
        ordinary_provider_factory=provider_factory,
    )

    with pytest.raises(QueryAuthorityError, match="active Profile"):
        client.query_granted(
            "construction-details",
            "When does it open?",
        )
    assert provider_called is False


def test_provider_connection_failure_is_publicly_typed(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    ops.add(context, "Fact.")
    store.save(context)

    def unavailable():
        raise RuntimeError("provider unavailable")

    client = MemCommitClient(
        root=isolated_store,
        ordinary_provider_factory=unavailable,
    )

    with pytest.raises(QueryProviderFailure, match="provider unavailable"):
        client.query_ordinary("Question?", context_names=("notes",))


def test_public_input_and_context_failures_are_typed_before_provider(tmp_path):
    provider_called = False

    def provider_factory():
        nonlocal provider_called
        provider_called = True
        return _OrdinaryProvider()

    client = MemCommitClient(
        root=tmp_path / "store",
        ordinary_provider_factory=provider_factory,
    )

    with pytest.raises(QueryInputError):
        client.query_ordinary("Question?", context_names="not-a-sequence")
    with pytest.raises(QueryContextError):
        client.query_ordinary("Question?", context_names=("missing",))
    assert provider_called is False


def test_public_api_modules_have_no_command_or_terminal_dependency():
    root = Path(__file__).parents[1] / "src" / "memcommit" / "api"
    imported: list[str] = []
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)

    forbidden = ("memcommit.commands", "typer", "prompt_toolkit")
    assert not any(name.startswith(forbidden) for name in imported)
