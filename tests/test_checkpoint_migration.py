"""Repair contracts for checkpoint locator fields missed by old Rename."""

from __future__ import annotations

import json

import pytest

import memcommit.application.ops as ops
from memcommit.application.retained_history.checkpoint_migration import (
    apply_rename_history_repair,
    plan_rename_history_repair,
)
from memcommit.application.retained_history.command_history import CommandHistoryError, build_command_stacks
from memcommit.core.context import AutoCheckpoint
from memcommit.persistence.store import MemoryStore


def _legacy_renamed_history(store: MemoryStore):
    source = ops.init("old")
    ops.add(source, "version one")
    store.save(
        source,
        AutoCheckpoint(
            command="init",
            args={"name": "old"},
            description="Initialized old",
        ),
    )
    source_memory = next(iter(source.iter_items()))
    observer = ops.init("observer")
    observer.add(source)
    memory_ref = ops.embed_memory(source_memory, source, observer)
    store.save(
        observer,
        AutoCheckpoint(
            command="reference",
            args={},
            description="Saved pointers",
        ),
    )
    observer.remove(source.uid)
    observer.remove(memory_ref.uid)
    removed = store.save(
        observer,
        AutoCheckpoint(
            command="remove",
            args={},
            description="Removed pointers",
        ),
    )
    assert removed is not None
    store.rename_contexts(store.plan_context_rename("old", "new"))

    checkpoint_path = next(
        path
        for path in store._checkpoints_dir("observer").glob(
            f"*-{removed.uid[:8]}.json"
        )
    )
    record = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    record["command_before"]["memories"][source.uid]["name"] = "old"
    record["command_before"]["memories"][memory_ref.uid]["target_context"][
        "name"
    ] = "old"
    checkpoint_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return source, memory_ref, checkpoint_path


def test_repair_migrates_exact_legacy_preimages_and_verifies_stack(isolated_store):
    store = MemoryStore()
    source, memory_ref, _checkpoint_path = _legacy_renamed_history(store)
    with pytest.raises(CommandHistoryError, match="pre-image conflicts"):
        build_command_stacks(store)

    plan = plan_rename_history_repair(
        store,
        context_uid=source.uid,
        old_name="old",
        new_name="new",
    )

    assert len(plan.changed_checkpoint_files) == 1
    assert plan.changed_reference_count == 2
    result = apply_rename_history_repair(
        store,
        context_uid=source.uid,
        old_name="old",
        new_name="new",
        expected_plan_digest=plan.plan_digest,
    )
    assert result.undo_depth == len(build_command_stacks(store).undo)
    assert result.redo_depth == 0

    store.restore_recent_context_command("undo")
    restored = store.load("observer")
    assert restored.memories[source.uid].name == "new"
    assert restored.memories[memory_ref.uid].target_context_name == "new"


def test_repair_rejects_a_stale_checkpoint_graph(isolated_store):
    store = MemoryStore()
    source, _memory_ref, checkpoint_path = _legacy_renamed_history(store)
    plan = plan_rename_history_repair(
        store,
        context_uid=source.uid,
        old_name="old",
        new_name="new",
    )
    record = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    record["message"] = "concurrent history change"
    checkpoint_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="changed after the repair was reviewed"):
        apply_rename_history_repair(
            store,
            context_uid=source.uid,
            old_name="old",
            new_name="new",
            expected_plan_digest=plan.plan_digest,
        )
