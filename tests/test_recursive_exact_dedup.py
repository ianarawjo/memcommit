"""Lexical-scope contracts for provider-free Find Duplicates and Dedup."""

from __future__ import annotations

import uuid

import pytest

import memcommit.application.capabilities.ops as ops
import memcommit.application.operations.find_duplicates.application as find_duplicates_application
from memcommit.adapters.python_api import MemCommitClient
from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.capabilities.command_recovery import build_command_stacks
from memcommit.core.context import MemoryRef
from memcommit.application.operations.dedup.application import (
    ExactDedupError,
    apply_exact_dedup_scope,
)
from memcommit.application.operations.find_duplicates.application import (
    analyze_exact_duplicate_scope,
)
from memcommit.persistence.store import MemoryStore


def _recursive_fixture(store: MemoryStore):
    root = ops.init("dedup/tree")
    root_first = ops.add(root, "root duplicate")
    root_later = ops.add(root, "root duplicate")
    child = ops.init("dedup/tree/child")
    child_first = ops.add(child, "child duplicate")
    child_later = ops.add(child, "child duplicate")
    sibling = ops.init("dedup/sibling")
    sibling_memory = ops.add(sibling, "root duplicate")
    for context in (root, child, sibling):
        store.save(context)
    store.set_current(root.name)
    return (
        root,
        root_first,
        root_later,
        child,
        child_first,
        child_later,
        sibling,
        sibling_memory,
    )


def test_public_find_duplicates_recursive_preserves_context_boundaries(
    isolated_store,
):
    store = MemoryStore()
    (
        root,
        root_first,
        root_later,
        child,
        child_first,
        child_later,
        sibling,
        sibling_memory,
    ) = _recursive_fixture(store)
    before = {
        name: store._context_file(name).read_bytes()
        for name in store.list_context_names()
    }

    result = MemCommitClient(root=isolated_store, create=False).find_duplicates(
        root.name,
        include_descendants=True,
    )

    assert result.context_name == root.name
    assert result.include_descendants is True
    assert [frame.context_name for frame in result.contexts] == [root.name, child.name]
    assert result.duplicate_count == 2
    groups = {group.context_name: group for group in result.groups}
    assert groups[root.name].survivor_uid == root_first.uid
    assert groups[root.name].absorbed_uids == (root_later.uid,)
    assert groups[child.name].survivor_uid == child_first.uid
    assert groups[child.name].absorbed_uids == (child_later.uid,)
    assert sibling_memory.uid not in {
        uid for group in result.groups for uid in group.absorbed_uids
    }
    assert {
        name: store._context_file(name).read_bytes()
        for name in store.list_context_names()
    } == before
    assert store.list_checkpoints(root.name) == []
    assert store.list_checkpoints(child.name) == []
    assert store.list_checkpoints(sibling.name) == []


def test_public_dedup_recursive_is_one_atomic_undoable_command(isolated_store):
    store = MemoryStore()
    (
        root,
        root_first,
        root_later,
        child,
        child_first,
        child_later,
        sibling,
        sibling_memory,
    ) = _recursive_fixture(store)

    result = MemCommitClient(root=isolated_store, create=False).dedup(
        root.name,
        include_descendants=True,
    )

    assert result.include_descendants is True
    assert result.removed_count == 2
    assert len(result.checkpoint_uids) == 2
    assert result.operation_uid is not None
    assert tuple(store.load_direct(root.name).memories) == (root_first.uid,)
    assert tuple(store.load_direct(child.name).memories) == (child_first.uid,)
    assert tuple(store.load_direct(sibling.name).memories) == (sibling_memory.uid,)
    stacks = build_command_stacks(store)
    assert stacks.undo[-1].uid == f"dedup:{result.operation_uid}"
    assert {change.context_name for change in stacks.undo[-1].changes} == {
        root.name,
        child.name,
    }

    restored = store.restore_recent_context_command("undo")

    assert restored.unit.uid == f"dedup:{result.operation_uid}"
    assert tuple(store.load_direct(root.name).memories) == (
        root_first.uid,
        root_later.uid,
    )
    assert tuple(store.load_direct(child.name).memories) == (
        child_first.uid,
        child_later.uid,
    )


def test_public_dedup_analyzes_each_context_exactly_once(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root, *_middle, child, _child_first, _child_later, _sibling, _sibling_memory = (
        _recursive_fixture(store)
    )
    analyzed_names: list[str] = []
    original = find_duplicates_application.find_exact_duplicate_groups

    def counted(context):
        analyzed_names.append(context.name)
        return original(context)

    monkeypatch.setattr(
        find_duplicates_application,
        "find_exact_duplicate_groups",
        counted,
    )

    MemCommitClient(root=isolated_store, create=False).dedup(
        root.name,
        include_descendants=True,
    )

    assert analyzed_names == [root.name, child.name]


def test_exact_dedup_rejects_a_stale_find_duplicates_analysis(isolated_store):
    store = MemoryStore()
    root, *_rest = _recursive_fixture(store)
    access = resolve_context_access(
        store,
        root.name,
        current_name=root.name,
        required_permission="READ",
    )
    analysis = analyze_exact_duplicate_scope(
        store,
        access,
        include_descendants=False,
    )
    changed = store.load_direct(root.name)
    ops.add(changed, "new after analysis")
    store.save(changed)

    with pytest.raises(ExactDedupError, match="changed after analysis"):
        apply_exact_dedup_scope(store, access, analysis)

    assert len(store.load_direct(root.name).memories) == 3
    assert store.list_checkpoints(root.name) == []


def test_recursive_exact_dedup_rolls_back_every_context_after_write_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    root, *_rest = _recursive_fixture(store)
    before = {
        name: store._context_file(name).read_bytes()
        for name in store.list_context_names()
    }
    access = resolve_context_access(
        store,
        root.name,
        current_name=root.name,
        required_permission="READ",
    )
    original_save = store._save_locked
    calls = 0

    def fail_second_write(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated second Context failure")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(store, "_save_locked", fail_second_write)
    analysis = analyze_exact_duplicate_scope(
        store,
        access,
        include_descendants=True,
    )

    with pytest.raises(OSError, match="simulated second Context failure"):
        apply_exact_dedup_scope(
            store,
            access,
            analysis,
        )

    assert {
        name: store._context_file(name).read_bytes()
        for name in store.list_context_names()
    } == before
    assert all(
        store.list_checkpoints(name) == [] for name in store.list_context_names()
    )


def test_recursive_exact_dedup_blocks_inbound_reference_before_any_write(
    isolated_store,
):
    store = MemoryStore()
    (
        root,
        root_first,
        root_later,
        child,
        child_first,
        child_later,
        sibling,
        _sibling_memory,
    ) = _recursive_fixture(store)
    sibling.add(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=child.uid,
            target_context_name=child.name,
            target_memory_uid=child_later.uid,
        )
    )
    store.save(sibling)
    access = resolve_context_access(
        store,
        root.name,
        current_name=root.name,
        required_permission="READ",
    )
    analysis = analyze_exact_duplicate_scope(
        store,
        access,
        include_descendants=True,
    )

    with pytest.raises(ExactDedupError, match="inbound reference"):
        apply_exact_dedup_scope(
            store,
            access,
            analysis,
        )

    assert tuple(store.load_direct(root.name).memories) == (
        root_first.uid,
        root_later.uid,
    )
    assert child_first.uid in store.load_direct(child.name).memories
    assert child_later.uid in store.load_direct(child.name).memories
    assert store.list_checkpoints(root.name) == []
    assert store.list_checkpoints(child.name) == []
