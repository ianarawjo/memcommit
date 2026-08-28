"""Public Python projection of read-only Show inspection."""

from __future__ import annotations

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import (
    MemCommitClient,
    ShowContextError,
    ShowContextResult,
    ShowInputError,
    ShowMemoryResult,
    ShowQueryViewResult,
)
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore


def _store_with_items(root):
    store = MemoryStore(root=root)
    child = ops.init("project/child")
    child_memory = ops.add(child, "child fact")
    store.save(child)
    parent = ops.init("project")
    parent_memory = ops.add(parent, "parent fact")
    ops.embed(child, parent)
    query = ops.reference_query_context(
        "project/concealed",
        "source-identity-never-opened",
        parent,
    )
    store.save(parent)
    store.set_current(parent.name)
    return store, parent_memory, child_memory, query


def test_client_shows_current_context_and_one_memory_without_provider(tmp_path):
    root = tmp_path / "store"
    store, parent_memory, _child_memory, _query = _store_with_items(root)

    def provider():
        raise AssertionError("Show must not connect a provider")

    client = MemCommitClient(root=root, semantic_provider_factory=provider)
    checkpoints_before = store.list_checkpoints("project")

    context = client.show()
    memory = client.show(parent_memory.uid[:8])

    assert isinstance(context, ShowContextResult)
    assert context.name == "project"
    assert [item.kind for item in context.items] == [
        "memory",
        "context",
        "query_view",
    ]
    assert isinstance(memory, ShowMemoryResult)
    assert memory.content == "parent fact"
    assert store.list_checkpoints("project") == checkpoints_before


def test_client_selects_embedded_context_by_exact_name(tmp_path):
    root = tmp_path / "store"
    _store_with_items(root)

    result = MemCommitClient(root=root).show("project/child")

    assert isinstance(result, ShowContextResult)
    assert result.name == "project/child"
    assert [item.content for item in result.items] == ["child fact"]


def test_query_view_is_structurally_concealed(tmp_path, monkeypatch):
    root = tmp_path / "store"
    _store, _memory, _child_memory, query = _store_with_items(root)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Show opened a query-only source")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)

    result = MemCommitClient(root=root).show(query.uid[:8])

    assert isinstance(result, ShowQueryViewResult)
    assert result.name == "project/concealed"
    assert not hasattr(result, "content")


def test_explicit_root_never_consults_global_profile_grants(tmp_path, monkeypatch):
    root = tmp_path / "store"
    _store_with_items(root)

    def forbidden():
        raise AssertionError("Explicit-root Show consulted global Profiles")

    monkeypatch.setattr(
        "memcommit.adapters.python_api._operations.show.load_profile_registry",
        forbidden,
    )

    result = MemCommitClient(root=root).show(context_name="project")

    assert isinstance(result, ShowContextResult)


def test_unknown_context_and_ambiguous_selector_use_public_errors(tmp_path):
    root = tmp_path / "store"
    store, _memory, _child_memory, _query = _store_with_items(root)
    context = store.load("project")
    context.add(Memory(uid="aaaa1111-1111-1111-1111-111111111111", content="one"))
    context.add(Memory(uid="aaaa2222-2222-2222-2222-222222222222", content="two"))
    store.save(context)
    client = MemCommitClient(root=root)

    with pytest.raises(ShowContextError, match="missing"):
        client.show(context_name="missing")
    with pytest.raises(ShowInputError, match="Ambiguous selector"):
        client.show("aaaa")
