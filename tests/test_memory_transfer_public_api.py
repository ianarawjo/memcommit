"""Stable Python facade contracts for direct-Memory Copy and Move."""

from __future__ import annotations

import pytest

import memcommit
import memcommit.ops as ops
from memcommit.api import (
    CopyMemoriesReceipt,
    MemCommitClient,
    MemoryTransferInputError,
    MoveMemoriesReceipt,
)
from memcommit.store import MemoryStore


def _fixture(root):
    store = MemoryStore(root=root)
    source = ops.init("source")
    first = ops.add(source, "first")
    second = ops.add(source, "second")
    target = ops.init("target")
    marker = ops.add(target, "marker")
    store.save(source)
    store.save(target)
    store.set_current(target.name)
    return store, source, first, second, target, marker


def test_root_package_exports_memory_transfer_values():
    assert memcommit.CopyMemoriesReceipt is CopyMemoriesReceipt
    assert memcommit.MoveMemoriesReceipt is MoveMemoriesReceipt
    assert memcommit.MemoryTransferInputError is MemoryTransferInputError


def test_public_copy_and_move_return_typed_undoable_receipts(tmp_path):
    root = tmp_path / "store"
    store, source, first, second, target, marker = _fixture(root)
    client = MemCommitClient(root=root)

    copied = client.copy_memories(
        (first.uid[:8],),
        source_context=source.name,
        before=marker.uid[:8],
    )
    moved = client.move_memories(
        (second.uid[:8],),
        source_context=source.name,
        into_context=target.name,
    )

    assert isinstance(copied, CopyMemoriesReceipt)
    assert copied.undoable is True
    assert not hasattr(copied, "uid_policy")
    assert copied.items[0].source_memory_uid == first.uid
    assert copied.items[0].into_memory_uid != first.uid
    assert isinstance(moved, MoveMemoriesReceipt)
    assert moved.undoable is True
    assert moved.link_policy == "RETARGET"
    assert moved.items[0].source_memory_uid == second.uid
    assert moved.items[0].into_memory_uid == second.uid
    assert list(store.load_direct(source.name).memories) == [first.uid]
    assert [item.content for item in store.load_direct(target.name).iter_items()] == [
        "first",
        "marker",
        "second",
    ]


def test_public_transfer_rejects_string_sequence_and_conflicting_link_policy(
    tmp_path,
):
    root = tmp_path / "store"
    _store, source, first, _second, target, _marker = _fixture(root)
    client = MemCommitClient(root=root)

    with pytest.raises(MemoryTransferInputError, match="sequence"):
        client.copy_memories(first.uid, into_context=target.name)
    with pytest.raises(TypeError, match="preserve_uids"):
        client.copy_memories(
            (first.uid,),
            into_context=target.name,
            preserve_uids=True,
        )
    with pytest.raises(MemoryTransferInputError, match="only one"):
        client.move_memories(
            (first.uid,),
            source_context=source.name,
            into_context=target.name,
            retarget_links=True,
            break_links=True,
        )
