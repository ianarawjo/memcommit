"""Global command-unit contracts for ``mem undo`` and ``mem redo``."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.command_recovery import (
    CommandHistoryError,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    build_history,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    reconstruct_memory_history,
)
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_undo_restores_the_previous_distinct_context_state(isolated_store):
    invoke("init", "notes")
    invoke("add", "keep")
    invoke("add", "undo me")

    result = invoke("undo")

    assert result.exit_code == 0
    assert "Undid command: mem add" in result.output
    assert "Affected Contexts: 1" in result.output
    assert "Affected Memories: 1 · - 1 removed" in result.output
    contents = [
        memory.content for memory in MemoryStore().load_current().memories.values()
    ]
    assert contents == ["keep"]


def test_undo_skips_manual_checkpoints_with_the_same_snapshot(isolated_store):
    invoke("init", "notes")
    invoke("add", "keep")
    invoke("checkpoint", "duplicate one")
    invoke("checkpoint", "duplicate two")

    result = invoke("undo")

    assert result.exit_code == 0
    assert "Undid command: mem add" in result.output
    assert not MemoryStore().load_current().memories


def test_undo_after_revert_restores_the_pre_revert_state(isolated_store):
    invoke("init", "notes")
    store = MemoryStore()
    init_uid = store.list_checkpoints("notes")[0]["uid"]
    invoke("add", "restore me")
    invoke("revert", init_uid[:8])
    assert not store.load_current().memories

    result = invoke("undo")

    assert result.exit_code == 0
    assert "Undid command: mem revert" in result.output
    restored = store.load_current()
    assert [memory.content for memory in restored.memories.values()] == ["restore me"]


def test_undo_rejects_unrecorded_change_after_latest_command(
    isolated_store,
):
    invoke("init", "notes")
    invoke("add", "saved")
    store = MemoryStore()
    context = store.load_current()
    context.add("not checkpointed")
    store.save(context)

    result = invoke("undo")

    assert result.exit_code == 1
    assert "changed after the command selected for undo" in result.output
    current = store.load_current()
    assert [memory.content for memory in current.memories.values()] == [
        "saved",
        "not checkpointed",
    ]


def test_undo_normalizes_inherited_checkpoint_identity(isolated_store):
    invoke("init", "source")
    invoke("add", "inherited")
    invoke("branch", "branch")
    invoke("add", "branch only")

    result = invoke("undo")

    assert result.exit_code == 0
    restored = MemoryStore().load_current()
    assert restored.name == "branch"
    assert [memory.content for memory in restored.memories.values()] == ["inherited"]


def test_undo_immediately_after_branch_cancels_the_created_context(
    isolated_store,
):
    invoke("init", "source")
    invoke("add", "inherited")
    store = MemoryStore()
    source_record = store.load_direct("source").to_dict()
    source_history = store.list_checkpoints("source")

    branched = invoke("branch", "feature")

    assert branched.exit_code == 0, branched.output
    branch_record = store.load_direct("feature").to_dict()
    branch_uid = branch_record["uid"]
    branch_history_uids = [entry["uid"] for entry in store.list_checkpoints("feature")]
    assert store.current_context_name() == "feature"

    undone = invoke("undo")

    assert undone.exit_code == 0, undone.output
    assert (
        "Undid command: mem branch feature --from source --source-root-only"
        in undone.output
    )
    assert not store.context_exists("feature")
    assert store.current_context_name() == "source"
    assert store.load_direct("source").to_dict() == source_record
    assert store.list_checkpoints("source") == source_history
    archived = store.list_command_context_archives()
    assert len(archived) == 1
    assert archived[0][0].uid == branch_uid

    redone = invoke("redo")

    assert redone.exit_code == 0, redone.output
    assert (
        "Redid command: mem branch feature --from source --source-root-only"
        in redone.output
    )
    assert store.load_direct("feature").to_dict() == branch_record
    assert store.current_context_name() == "feature"
    restored_history_uids = [
        entry["uid"] for entry in store.list_checkpoints("feature")
    ]
    assert restored_history_uids[-len(branch_history_uids) :] == branch_history_uids
    assert store.list_command_context_archives() == ()


def test_branch_restore_preserves_a_later_unrelated_current_selection(
    isolated_store,
):
    invoke("init", "source")
    invoke("add", "source fact")
    invoke("init", "other")
    invoke("switch", "source")
    invoke("branch", "feature")
    invoke("switch", "other")
    store = MemoryStore()

    undone = invoke("undo")

    assert undone.exit_code == 0, undone.output
    assert not store.context_exists("feature")
    assert store.current_context_name() == "other"

    redone = invoke("redo")

    assert redone.exit_code == 0, redone.output
    assert store.context_exists("feature")
    assert store.current_context_name() == "other"


def test_branch_redo_does_not_replace_a_new_context_with_the_same_name(
    isolated_store,
):
    invoke("init", "source")
    invoke("add", "source fact")
    invoke("branch", "feature")
    store = MemoryStore()
    original_branch_uid = store.load_direct("feature").uid
    assert invoke("undo").exit_code == 0
    competitor = ops.init("feature")
    competitor.add("independent replacement")
    store.save(competitor)

    redone = invoke("redo")

    assert redone.exit_code == 1
    assert "Affected Context 'feature' already exists" in redone.output
    current = store.load_direct("feature")
    assert current.uid == competitor.uid
    assert current.uid != original_branch_uid
    assert [memory.content for memory in current.memories.values()] == [
        "independent replacement"
    ]


def test_undo_fails_without_a_recorded_context_command(isolated_store):
    store = MemoryStore()
    context = ops.init("bare")
    store.save(context)
    store.set_current("bare")

    result = invoke("undo")

    assert result.exit_code == 1
    assert "no recorded Context command to undo" in result.output


def test_undo_fails_without_a_current_context(isolated_store):
    result = invoke("undo")

    assert result.exit_code == 1
    assert "no recorded Context command to undo" in result.output


def test_undo_and_redo_follow_global_command_order_across_contexts(
    isolated_store,
):
    invoke("init", "first")
    invoke("add", "first change")
    invoke("init", "second")
    invoke("add", "second change")
    invoke("switch", "first")
    store = MemoryStore()

    first_undo = invoke("undo")

    assert first_undo.exit_code == 0, first_undo.output
    assert not store.load_direct("second").memories
    assert store.load_direct("first").memories

    second_undo = invoke("undo")

    assert second_undo.exit_code == 0, second_undo.output
    assert not store.load_direct("first").memories

    first_redo = invoke("redo")
    second_redo = invoke("redo")

    assert first_redo.exit_code == 0, first_redo.output
    assert "Redid command: mem add" in first_redo.output
    assert second_redo.exit_code == 0, second_redo.output
    assert store.load_direct("first").memories
    assert store.load_direct("second").memories


def test_new_command_after_undo_clears_redo_stack(isolated_store):
    invoke("init", "notes")
    invoke("add", "first")
    invoke("add", "discarded")
    assert invoke("undo").exit_code == 0
    invoke("add", "replacement")

    result = invoke("redo")

    assert result.exit_code == 1
    assert "no recorded Context command to redo" in result.output


def test_empty_stale_granted_receipt_does_not_mask_local_undo(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "remove locally")
    staged = type(
        "StagedGrantedUpdate",
        (),
        {"status": "applied", "granted_target": object()},
    )()
    monkeypatch.setattr(MemoryStore, "load_staged_update", lambda _store: staged)
    monkeypatch.setattr(
        "memcommit.application.operations.undo.runtime.restore_update_command",
        lambda *_args: (_ for _ in ()).throw(
            CommandHistoryError("There is no recorded Context command to undo.")
        ),
    )

    result = invoke("undo")

    assert result.exit_code == 0, result.output
    assert "Undid command: mem add" in result.output


def test_empty_stale_granted_receipt_does_not_mask_local_redo(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "restore locally")
    assert invoke("undo").exit_code == 0
    staged = type(
        "StagedGrantedUpdate",
        (),
        {"status": "undone", "granted_target": object()},
    )()
    monkeypatch.setattr(MemoryStore, "load_staged_update", lambda _store: staged)
    monkeypatch.setattr(
        "memcommit.application.operations.redo.runtime.restore_update_command",
        lambda *_args: (_ for _ in ()).throw(
            CommandHistoryError("There is no recorded Context command to redo.")
        ),
    )

    result = invoke("redo")

    assert result.exit_code == 0, result.output
    assert "Redid command: mem add" in result.output


def test_history_and_trace_keep_command_undo_and_redo_operation_boundaries(
    isolated_store,
):
    invoke("init", "notes")
    invoke("add", "restore through history")
    store = MemoryStore()

    assert invoke("undo").exit_code == 0
    assert invoke("redo").exit_code == 0
    timeline = build_history(store, "notes")

    restoration_commands = [
        (transition.command, transition.kind, transition.evidence)
        for transition in timeline.transitions
        if transition.command in {"undo", "redo"}
    ]
    assert restoration_commands == [
        ("undo", "RESTORED", "RECORDED"),
        ("redo", "RESTORED", "RECORDED"),
    ]

    context = store.load_direct("notes")
    memory = next(iter(context.memories.values()))
    report = reconstruct_memory_history(store, context, memory.uid)
    restoration_events = [
        event for event in report.events if event.command in {"undo", "redo"}
    ]

    assert [event.kind for event in restoration_events] == [
        "RESTORED",
        "RESTORED",
    ]
    assert [event.evidence for event in restoration_events] == [
        "RECORDED",
        "RECORDED",
    ]
    assert [
        event.command_operation.command
        for event in restoration_events
        if event.command_operation is not None
    ] == ["undo", "redo"]
    assert all(
        event.command_operation is not None
        and event.command_operation.source_command == "add"
        and [context.name for context in event.command_operation.contexts] == ["notes"]
        for event in restoration_events
    )

    rendered = invoke("trace", memory.uid[:8])

    assert rendered.exit_code == 0, rendered.output
    assert "[undo] [CHECKPOINT " in rendered.output
    assert "[redo] [CHECKPOINT " in rendered.output
    assert rendered.output.count("[SOURCE add ") == 2
    assert rendered.output.index("[redo] [CHECKPOINT ") < rendered.output.index(
        "[undo] [CHECKPOINT "
    )

    detailed = invoke("trace", memory.uid[:8], "--verbose")
    assert detailed.exit_code == 0, detailed.output
    assert "Operation: undo" in detailed.output
    assert "Operation: redo" in detailed.output
    assert detailed.output.count("Source operation: mem add") == 2
    assert detailed.output.count("Affected Context: notes") == 2
