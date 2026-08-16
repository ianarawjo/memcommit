"""Stable Python facade tests for deterministic Replace."""

from __future__ import annotations

import pytest

import memcommit.ops as ops
from memcommit.api import (
    MemCommitClient,
    ReplaceConflictError,
    ReplaceContextError,
    ReplaceInputError,
)
from memcommit.store import MemoryStore


def _client(tmp_path, *contents: str):
    root = tmp_path / "store"
    store = MemoryStore(root=root)
    context = ops.init("replace/source")
    for content in contents:
        ops.add(context, content)
    store.save(context)
    store.set_current(context.name)
    return MemCommitClient(root=root), store


def test_client_plans_then_applies_same_opaque_replace(tmp_path) -> None:
    client, store = _client(tmp_path, "needle and needle")

    plan = client.plan_replace("needle", "thread")

    assert plan.pattern == "needle"
    assert plan.replacement == "thread"
    assert plan.occurrence_count == 2
    assert plan.changed_memory_count == 1
    assert plan.contexts[0].matches[0].after_content == "thread and thread"
    assert store.list_checkpoints("replace/source") == []

    applied = client.apply_replace(plan)

    assert applied.applied is True
    assert applied.plan_digest == plan.plan_digest
    assert len(applied.checkpoints) == 1
    assert [
        memory.content
        for memory in store.load_direct("replace/source").memories.values()
    ] == ["thread and thread"]


def test_client_rejects_stale_or_foreign_replace_plan(tmp_path) -> None:
    client, store = _client(tmp_path, "needle")
    reviewed = client.plan_replace("needle", "thread")
    changed = store.load_direct("replace/source")
    changed.add("later")
    store.save(changed)

    with pytest.raises(ReplaceConflictError, match="changed"):
        client.apply_replace(reviewed)

    other = MemCommitClient(root=tmp_path / "other", create=True)
    with pytest.raises(ReplaceInputError, match="does not belong"):
        other.apply_replace(reviewed)


def test_client_replace_is_local_and_provider_free(tmp_path) -> None:
    client, _store = _client(tmp_path, "needle")

    def provider():
        raise AssertionError("Replace must not construct a provider")

    isolated = MemCommitClient(
        root=client.store_root,
        semantic_provider_factory=provider,
    )
    plan = isolated.plan_replace("needle", "thread")

    assert plan.occurrence_count == 1
    with pytest.raises(ReplaceContextError, match="ordinary local"):
        isolated.plan_replace("needle", "thread", ("missing",))
