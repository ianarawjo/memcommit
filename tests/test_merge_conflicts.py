"""Deterministic Merge conflict, resolution, and recovery contracts."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.direct_changes.merge.workbench.conflicts import (
    merge_resolution_spec,
)
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.direct_changes.merge.application import (
    MergeConflictKind,
    MergeDecision,
    MergeError,
    MergeReach,
    MergeRequest,
    merge_resolution_case,
    prepare_merge,
    resolve_merge_conflicts,
)
from memcommit.application.operations.direct_changes.merge.runtime import (
    MemoryStoreMergePort,
    execute_merge,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


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
    assert store.load_direct("target").memories["shared"].content == ("target revision")
    assert kept.resolutions[0].decision is MergeDecision.KEEP_TARGET

    taken = execute_merge(
        MergeRequest(source_locator="source"),
        store=store,
        bulk=MergeDecision.TAKE_SOURCE,
    )
    assert store.load_direct("target").memories["shared"].content == ("source revision")
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
    assert "SOURCE CONTENT · source revision" in unresolved.output
    assert "TARGET CONTENT · target revision" in unresolved.output
    assert "--keep-target-all / --take-source-all" in unresolved.output
    assert store.load_direct("target").memories["shared"].content == ("target revision")
    planned = prepare_merge(
        MergeRequest(source_locator="source"),
        port=MemoryStoreMergePort.capture(store),
    )

    resolved = runner.invoke(app, ["merge", "source", "--take-source-all"])
    assert resolved.exit_code == 0, resolved.output + resolved.stderr
    assert "TOOK SOURCE 1" in resolved.output
    assert "TARGET CHANGED YES" in resolved.output
    assert store.load_direct("target").memories["shared"].content == ("source revision")
    (checkpoint,) = store.list_checkpoints("target")
    assert checkpoint["args"]["merge_decisions"] == {
        "version": 1,
        "decisions": [
            {
                "conflict_uid": planned.conflicts[0].uid,
                "kind": "CONTENT_DIVERGENCE",
                "decision": "TAKE_SOURCE",
                "source_name": "source",
                "target_name": "target",
                "source_uid": "shared",
                "target_uids": ["shared"],
            }
        ],
    }
    assert "kept Target 0; took Source 1" in checkpoint["description"]


def test_keep_target_only_receipt_explains_the_zero_delta(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    source.add(Memory(uid="shared", content="source revision"))
    _create(store, source)
    target = ops.init("target")
    target.add(Memory(uid="shared", content="target revision"))
    _create(store, target)
    store.set_current("target")

    kept = runner.invoke(app, ["merge", "source", "--keep-target-all"])

    assert kept.exit_code == 0, kept.output + kept.stderr
    assert "NEW 0" in kept.output
    assert "ALREADY PRESENT 0" in kept.output
    assert "KEPT TARGET 1" in kept.output
    assert "TOOK SOURCE 0" in kept.output
    assert "TARGET CHANGED NO" in kept.output
    (checkpoint,) = store.list_checkpoints("target")
    assert (
        "new 0; already present 0; kept Target 1; took Source 0"
        in (checkpoint["description"])
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


def test_branch_fresh_uid_edits_unambiguously_and_merges_by_checkpoint_lineage(
    isolated_store,
):
    assert runner.invoke(app, ["init", "practice/greetings"]).exit_code == 0
    assert runner.invoke(app, ["add", "bonjour"]).exit_code == 0
    store = MemoryStore()
    source = store.load_current_direct()
    source_memory = next(
        item for item in source.iter_items() if isinstance(item, Memory)
    )

    branched = runner.invoke(app, ["branch", "practice/greetings2"])

    assert branched.exit_code == 0, branched.output
    branch = store.load_current_direct()
    branch_memory = next(
        item for item in branch.iter_items() if isinstance(item, Memory)
    )
    assert branch_memory.uid != source_memory.uid
    branch_checkpoint = store.list_checkpoints(branch.name)[0]
    [branch_edge] = branch_checkpoint["args"]["memory_lineage"]["edges"]
    assert branch_edge["source_memory_uid"] == source_memory.uid
    assert branch_edge["target_memory_uid"] == branch_memory.uid

    edited = runner.invoke(app, ["edit", branch_memory.uid[:4], "bonsoir"])

    assert edited.exit_code == 0, edited.output
    assert store.load_direct(source.name).memories[source_memory.uid].content == (
        "bonjour"
    )
    assert store.load_direct(branch.name).memories[branch_memory.uid].content == (
        "bonsoir"
    )

    assert runner.invoke(app, ["switch", source.name]).exit_code == 0
    unresolved = runner.invoke(app, ["merge", branch.name])
    assert unresolved.exit_code == 1
    assert "CONTENT_DIVERGENCE" in unresolved.output
    assert "SOURCE CONTENT · bonsoir" in unresolved.output
    assert "TARGET CONTENT · bonjour" in unresolved.output

    accepted = runner.invoke(app, ["merge", branch.name, "--take-source-all"])

    assert accepted.exit_code == 0, accepted.output + accepted.stderr
    merged = store.load_direct(source.name)
    assert list(merged.memories) == [source_memory.uid]
    assert merged.memories[source_memory.uid].content == "bonsoir"
    merge_checkpoint = store.list_checkpoints(source.name)[0]
    [merge_edge] = merge_checkpoint["args"]["memory_lineage"]["edges"]
    assert merge_edge["source_memory_uid"] == branch_memory.uid
    assert merge_edge["target_memory_uid"] == source_memory.uid

    repeated = runner.invoke(app, ["merge", branch.name])
    assert repeated.exit_code == 0, repeated.output + repeated.stderr
    assert "ALREADY PRESENT 1" in repeated.output
    assert len(store.load_direct(source.name).memories) == 1


def test_nested_branch_lineage_resolves_transitively_for_merge(isolated_store):
    assert runner.invoke(app, ["init", "main"]).exit_code == 0
    assert runner.invoke(app, ["add", "baseline"]).exit_code == 0
    store = MemoryStore()
    main = store.load_current_direct()
    main_memory = next(item for item in main.iter_items() if isinstance(item, Memory))

    assert runner.invoke(app, ["branch", "feature"]).exit_code == 0
    feature = store.load_current_direct()
    feature_memory = next(
        item for item in feature.iter_items() if isinstance(item, Memory)
    )
    assert runner.invoke(app, ["branch", "experiment"]).exit_code == 0
    experiment = store.load_current_direct()
    experiment_memory = next(
        item for item in experiment.iter_items() if isinstance(item, Memory)
    )
    assert len({main_memory.uid, feature_memory.uid, experiment_memory.uid}) == 3

    assert (
        runner.invoke(
            app, ["edit", experiment_memory.uid[:8], "experiment revision"]
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["switch", main.name]).exit_code == 0

    unresolved = runner.invoke(app, ["merge", experiment.name])

    assert unresolved.exit_code == 1
    assert "CONTENT_DIVERGENCE" in unresolved.output
    accepted = runner.invoke(app, ["merge", experiment.name, "--take-source-all"])
    assert accepted.exit_code == 0, accepted.output + accepted.stderr
    merged = store.load_direct(main.name)
    assert list(merged.memories) == [main_memory.uid]
    assert merged.memories[main_memory.uid].content == "experiment revision"


def test_merge_rejects_tampered_branch_lineage_before_target_write(
    isolated_store,
):
    assert runner.invoke(app, ["init", "main"]).exit_code == 0
    assert runner.invoke(app, ["add", "baseline"]).exit_code == 0
    store = MemoryStore()
    main = store.load_current_direct()
    main_digest = context_record_digest(main)
    assert runner.invoke(app, ["branch", "feature"]).exit_code == 0
    branch_checkpoint = store.list_checkpoints("feature")[0]
    checkpoint_path = next(
        (isolated_store / "contexts" / "feature" / "checkpoints").glob(
            f"*-{branch_checkpoint['uid'][:8]}.json"
        )
    )
    record = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    record["args"]["memory_lineage"]["edges"][0]["target_content_sha256"] = "0" * 64
    checkpoint_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    store.set_current(main.name)

    with pytest.raises(
        ValueError,
        match="does not match its target snapshot",
    ):
        execute_merge(MergeRequest(source_locator="feature"), store=store)

    unchanged = store.load_direct(main.name)
    assert context_record_digest(unchanged) == main_digest
    assert store.list_checkpoints(main.name)[0]["command"] == "add"


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
    assert (
        merge_resolution_case(first).binding.revision
        != merge_resolution_case(second).binding.revision
    )


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
    assert [strategy.choice_uid for strategy in spec.bulk_strategies] == ["KEEP_TARGET"]

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
    assert [strategy.choice_uid for strategy in spec.bulk_strategies] == ["KEEP_TARGET"]
    assert [choice.content for choice in spec.items[0].inline_choices] == [
        "source revision",
        "target revision",
    ]
    assert [choice.selectable for choice in spec.items[0].inline_choices] == [
        False,
        True,
    ]
    assert spec.items[0].default_choice_uid == "KEEP_TARGET"

    unresolved = runner.invoke(app, ["merge", "source"])
    assert unresolved.exit_code == 1
    assert "ALLOWED · KEEP_TARGET" in unresolved.output
    assert "--take-source-all" not in unresolved.output

    rejected = runner.invoke(app, ["merge", "source", "--take-source-all"])
    assert rejected.exit_code == 1
    assert "not authorized" in rejected.stderr
    assert store.load_direct("target").memories["shared"].content == ("target revision")

    kept = runner.invoke(app, ["merge", "source", "--keep-target-all"])
    assert kept.exit_code == 0, kept.output + kept.stderr
    assert store.load_direct("target").memories["shared"].content == ("target revision")


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
