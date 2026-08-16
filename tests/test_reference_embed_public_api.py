"""Stable Python facade tests for snapshot Reference and live Embed."""

from __future__ import annotations

import pytest

import memcommit.ops as ops
from memcommit.api import (
    EmbeddedContextResult,
    EmbeddedMemoryResult,
    EmbedInputError,
    MemCommitClient,
    MemoryReferenceResult,
    ReferenceContextError,
)
from memcommit.context import Memory, MemoryRef
from memcommit.store import MemoryStore


def _store(root):
    store = MemoryStore(root=root)
    source = ops.init("source")
    memory = ops.add(source, "version one")
    store.save(source)
    target = ops.init("target")
    marker = ops.add(target, "target marker")
    store.save(target)
    child = ops.init("child")
    store.save(child)
    store.set_current(target.name)
    return store, source, memory, target, marker, child


def test_public_reference_is_snapshot_while_memory_embed_is_live(tmp_path):
    root = tmp_path / "store"
    store, source, memory, _target, marker, _child = _store(root)
    client = MemCommitClient(root=root)

    snapshot = client.reference_memory(
        memory.uid[:8],
        source_context="source",
        into_context="target",
    )
    live = client.embed_memory(
        memory.uid[:8],
        source_context="source",
        into_context="target",
        before=marker.uid[:8],
    )

    assert isinstance(snapshot, MemoryReferenceResult)
    assert isinstance(live, EmbeddedMemoryResult)
    target = store.load("target")
    snapshot_item = target.memories[snapshot.reference_uid]
    live_item = target.memories[live.embed_uid]
    assert isinstance(snapshot_item, MemoryRef) and snapshot_item.is_snapshot
    assert isinstance(live_item, MemoryRef) and live_item.is_live
    assert live.placement.next_uid == marker.uid

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)
    reloaded = store.load("target")
    assert reloaded.memories[snapshot.reference_uid].target.content == "version one"
    assert reloaded.memories[live.embed_uid].target.content == "version two"


def test_public_context_embed_keeps_context_route_distinct(tmp_path):
    root = tmp_path / "store"
    store, _source, _memory, _target, _marker, child = _store(root)

    result = MemCommitClient(root=root).embed_context(
        "child",
        into_context="target",
    )

    assert isinstance(result, EmbeddedContextResult)
    assert result.child_uid == child.uid
    embedded = store.load("target").memories[result.child_uid]
    assert embedded.uid == child.uid
    assert embedded.name == result.child_name


def test_public_transfer_errors_are_operation_specific(tmp_path):
    root = tmp_path / "store"
    _store(root)
    client = MemCommitClient(root=root)

    with pytest.raises(ReferenceContextError, match="missing"):
        client.reference_memory("abcd", source_context="missing")
    with pytest.raises(EmbedInputError, match="only one"):
        client.embed_context(
            "child",
            into_context="target",
            before="aaaa",
            after="bbbb",
        )
