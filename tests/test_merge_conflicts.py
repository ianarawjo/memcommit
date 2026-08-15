"""Deterministic Merge conflict, resolution, and recovery contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.merge_application import (
    MergeConflictKind,
    MergeDecision,
    MergeError,
    MergeReach,
    MergeRequest,
    prepare_merge,
    resolve_merge_conflicts,
)
from memcommit.interfaces.tui.operations.merge import merge_resolution_spec
from memcommit.merge_runtime import MemoryStoreMergePort, execute_merge
from memcommit.store import MemoryStore, context_record_digest


runner = CliRunner(mix_stderr=False)


def _create(store: MemoryStore, context: Context) -> Context:
    store.create_context(context)
    return context


def test_plan_classifies_all_deterministic_collision_kinds(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    target = ops.init("target")
    source.add(Memory(uid="content", content="source"))
    target.add(Memory(uid="content", content="target"))
    source.add(Memory(uid="type", content="source type"))
    target.add(QueryContextRef("type", "placed/type", "type-source", "p"))
    source.add(
        MemoryRef(
            uid="source-ref",
            target_context_uid="owner",
            target_context_name="owner",
            target_memory_uid="memory",
        )
    )
    target.add(
        MemoryRef(
            uid="target-ref",
            target_context_uid="owner",
            target_context_name="owner",
            target_memory_uid="memory",
        )
    )
    source.add(QueryContextRef("source-place", "shared", "source-a", "p"))
    target.add(QueryContextRef("target-place", "shared", "source-b", "p"))
    _create(store, source)
    _create(store, target)
    store.set_current("target")

    plan = prepare_merge(
        MergeRequest(source_locator="source"),
        port=MemoryStoreMergePort.capture(store),
    )

    assert [conflict.kind for conflict in plan.conflicts] == [
        MergeConflictKind.CONTENT_DIVERGENCE,
        MergeConflictKind.TYPE_COLLISION,
        MergeConflictKind.REFERENCE_COLLISION,
        MergeConflictKind.PLACEMENT_COLLISION,
    ]
    assert len({conflict.uid for conflict in plan.conflicts}) == 4
    assert all(
        conflict.source_name == "source" and conflict.target_name == "target"
        for conflict in plan.conflicts
    )


def test_direct_conflict_requires_a_choice_and_applies_each_bulk_strategy(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("source")
    source.add(Memory(uid="shared", content="source revision"))
    _create(store, source)
    target = ops.init("target")
    target.add(Memory(uid="shared", content="target revision"))
    _create(store, target)
    store.set_current("target")

    kept = execute_merge(
        MergeRequest(source_locator="source"),
        store=store,
        bulk=MergeDecision.KEEP_TARGET,
    )
    assert store.load_direct("target").memories["shared"].content == (
        "target revision"
    )
    assert kept.resolutions[0].decision is MergeDecision.KEEP_TARGET

    taken = execute_merge(
        MergeRequest(source_locator="source"),
        store=store,
        bulk=MergeDecision.TAKE_SOURCE,
    )
    assert store.load_direct("target").memories["shared"].content == (
        "source revision"
    )
    assert taken.resolutions[0].decision is MergeDecision.TAKE_SOURCE


def test_noninteractive_cli_lists_ids_then_accepts_a_bulk_resolution(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("source")
    source.add(Memory(uid="shared", content="source revision"))
    _create(store, source)
    target = ops.init("target")
    target.add(Memory(uid="shared", content="target revision"))
    _create(store, target)
    store.set_current("target")

    unresolved = runner.invoke(app, ["merge", "source"])
    assert unresolved.exit_code == 1
    assert "CONTENT_DIVERGENCE" in unresolved.output
    assert "--keep-target-all / --take-source-all" in unresolved.output
    assert store.load_direct("target").memories["shared"].content == (
        "target revision"
    )

    resolved = runner.invoke(app, ["merge", "source", "--take-source-all"])
    assert resolved.exit_code == 0, resolved.output + resolved.stderr
    assert "resolved 1 conflict" in resolved.output
    assert store.load_direct("target").memories["shared"].content == (
        "source revision"
    )


def test_recursive_merge_is_one_undo_redo_unit_including_created_contexts(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "root addition")
    _create(store, source)
    child = ops.init("source/child")
    ops.add(child, "child addition")
    _create(store, child)
    target = _create(store, ops.init("target"))
    store.set_current(target.name)

    execute_merge(
        MergeRequest(source_locator="source", reach=MergeReach.DESCENDANTS),
        store=store,
    )
    assert store.context_exists("target/child")

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output + undone.stderr
    assert tuple(store.load_direct("target").iter_items()) == ()
    assert not store.context_exists("target/child")
    assert "Affected Contexts: 2" in undone.output

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output + redone.stderr
    assert [item.content for item in store.load_direct("target").iter_items()] == [
        "root addition"
    ]
    assert [
        item.content for item in store.load_direct("target/child").iter_items()
    ] == ["child addition"]


def test_noop_merge_remains_an_undoable_boundary(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    source.add(Memory(uid="same", content="same"))
    _create(store, source)
    target = ops.init("target")
    target.add(Memory(uid="same", content="same"))
    _create(store, target)
    store.set_current("target")

    result = execute_merge(MergeRequest(source_locator="source"), store=store)
    assert result.additions == ()
    assert len(result.unchanged) == 1

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output + undone.stderr
    assert store.load_direct("target").memories["same"].content == "same"


def test_conflict_identity_changes_when_frozen_content_changes(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    source.add(Memory(uid="shared", content="source revision one"))
    _create(store, source)
    target = ops.init("target")
    target.add(Memory(uid="shared", content="target revision"))
    _create(store, target)
    store.set_current("target")

    first = prepare_merge(
        MergeRequest(source_locator="source"),
        port=MemoryStoreMergePort.capture(store),
    )
    updated = store.load_for_update("source")
    updated.memories["shared"] = Memory(
        uid="shared",
        content="source revision two",
    )
    store.save(updated, expected_context_digest=updated._store_digest)
    second = prepare_merge(
        MergeRequest(source_locator="source"),
        port=MemoryStoreMergePort.capture(store),
    )

    assert first.conflicts[0].uid != second.conflicts[0].uid


def test_restricted_conflict_never_promises_take_source(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    source.add(Memory(uid="shared", content="source revision"))
    _create(store, source)
    target = ops.init("target")
    target.add(Memory(uid="shared", content="target revision"))
    _create(store, target)
    store.set_current("target")
    plan = prepare_merge(
        MergeRequest(source_locator="source"),
        port=MemoryStoreMergePort.capture(store),
    )
    restricted_conflict = replace(
        plan.conflicts[0],
        allowed_decisions=(MergeDecision.KEEP_TARGET,),
    )
    restricted_context = replace(
        plan.contexts[0],
        conflicts=(restricted_conflict,),
    )
    restricted_plan = replace(
        plan,
        contexts=(restricted_context,),
        conflicts=(restricted_conflict,),
    )

    spec = merge_resolution_spec(restricted_plan)

    assert [choice.uid for choice in spec.items[0].choices] == ["KEEP_TARGET"]
    assert [strategy.choice_uid for strategy in spec.bulk_strategies] == [
        "KEEP_TARGET"
    ]

    with pytest.raises(MergeError, match="not authorized"):
        resolve_merge_conflicts(
            restricted_plan,
            bulk=MergeDecision.TAKE_SOURCE,
        )


def test_protected_target_memory_never_promises_take_source(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    source.add(Memory(uid="shared", content="source revision"))
    _create(store, source)
    target = ops.init("target")
    target.add(Memory(uid="shared", content="target revision"))
    _create(store, target)
    store.set_current("target")
    store.set_memory_write_protection(
        "target",
        "shared",
        protected=True,
        expected_context_uid=target.uid,
        expected_context_digest=context_record_digest(target),
    )

    plan = prepare_merge(
        MergeRequest(source_locator="source"),
        port=MemoryStoreMergePort.capture(store),
    )
    spec = merge_resolution_spec(plan)

    assert plan.conflicts[0].allowed_decisions == (MergeDecision.KEEP_TARGET,)
    assert [choice.uid for choice in spec.items[0].choices] == ["KEEP_TARGET"]
    assert [strategy.choice_uid for strategy in spec.bulk_strategies] == [
        "KEEP_TARGET"
    ]

    unresolved = runner.invoke(app, ["merge", "source"])
    assert unresolved.exit_code == 1
    assert "ALLOWED · KEEP_TARGET" in unresolved.output
    assert "--take-source-all" not in unresolved.output

    rejected = runner.invoke(app, ["merge", "source", "--take-source-all"])
    assert rejected.exit_code == 1
    assert "not authorized" in rejected.stderr
    assert store.load_direct("target").memories["shared"].content == (
        "target revision"
    )

    kept = runner.invoke(app, ["merge", "source", "--keep-target-all"])
    assert kept.exit_code == 0, kept.output + kept.stderr
    assert store.load_direct("target").memories["shared"].content == (
        "target revision"
    )


def test_protected_target_context_rejects_unconditional_addition_before_review(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "new source fact")
    _create(store, source)
    target = _create(store, ops.init("target"))
    store.set_current(target.name)
    store.set_context_write_protection(
        "target",
        protected=True,
        expected_context_uid=target.uid,
        expected_context_digest=context_record_digest(target),
    )

    with pytest.raises(RuntimeError, match="locked against changes"):
        prepare_merge(
            MergeRequest(source_locator="source"),
            port=MemoryStoreMergePort.capture(store),
        )
