"""Checkpoint-to-picker projection contracts."""
from __future__ import annotations

from memcommit.commands.shared.history_present import checkpoint_picker_entries
from memcommit.application.retained_history.reconstruction import HistoryState, MemoryTransition, MemoryVersion
from memcommit.application.operations.log.search import HistorySearchResult


def checkpoint(
    uid: str,
    timestamp: str,
    memories: dict,
    order: list[str],
) -> dict:
    return {
        "uid": uid,
        "timestamp": timestamp,
        "command": "edit",
        "description": "Changed facilities",
        "snapshot": {
            "uid": "context",
            "name": "wiki",
            "memories": memories,
            "order": order,
        },
    }


def test_checkpoint_projection_summarizes_snapshot_and_transition():
    first = checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-07-30T10:00:00",
        {
            "m1": {"type": "memory", "uid": "m1", "content": "old"},
            "r1": {
                "type": "query_context_ref",
                "uid": "r1",
                "name": "origin",
            },
        },
        ["m1", "r1"],
    )
    second = checkpoint(
        "22222222-2222-4222-8222-222222222222",
        "2026-07-30T11:00:00",
        {
            "m1": {"type": "memory", "uid": "m1", "content": "new"},
            "m2": {"type": "memory", "uid": "m2", "content": "added"},
        },
        ["m2", "m1"],
    )

    entries = checkpoint_picker_entries([second, first])

    assert entries[0].uid == second["uid"]
    assert "2 direct items · 2 Memories" in entries[0].detail
    assert "+1 added · ~1 edited · -1 removed · 1 reordered" in entries[0].detail
    assert "baseline" in entries[1].detail


def test_checkpoint_projection_appends_mutation_preview():
    value = checkpoint(
        "11111111-1111-4111-8111-111111111111",
        "2026-07-30T10:00:00",
        {},
        [],
    )

    entries = checkpoint_picker_entries(
        [value],
        extra_detail_by_uid={
            value["uid"]: "Revert: 3 newer checkpoints will leave the active log",
        },
    )

    assert "Revert: 3 newer checkpoints" in entries[0].detail


def test_semantic_memory_version_projection_keeps_checkpoint_boundary():
    version = MemoryVersion(
        context_uid="context",
        context_name="wiki",
        memory_uid="memory",
        content="The shuttle notice was active.",
        content_digest="digest",
    )
    state = HistoryState(
        index=2,
        checkpoint_uid="22222222-2222-4222-8222-222222222222",
        timestamp="2026-07-30T11:00:00",
        command="edit",
        description="Updated shuttle",
        memories=(version,),
        record_digest="record",
        selectable=True,
    )
    result = HistorySearchResult(
        candidate_id="v000001",
        kind="memory_version",
        context_uid="context",
        context_name="wiki",
        checkpoint_uid=state.checkpoint_uid,
        timestamp=state.timestamp,
        description=version.content,
        selectable=True,
        state=state,
        memory_version=version,
    )

    from memcommit.commands.shared.history_present import (
        history_result_picker_entries,
    )

    entry = history_result_picker_entries([result])[0]
    assert entry.uid == "v000001"
    assert state.checkpoint_uid in entry.detail
    assert version.content in entry.detail
    assert "restorable via checkpoint 22222222" in entry.detail


def test_semantic_checkpoint_projection_distinguishes_active_and_archived():
    state = HistoryState(
        index=2,
        checkpoint_uid="22222222-2222-4222-8222-222222222222",
        timestamp="2026-07-30T11:00:00",
        command="edit",
        description="Updated shuttle",
        memories=(),
        record_digest="record",
        selectable=True,
    )
    common = {
        "candidate_id": "p000001",
        "kind": "checkpoint",
        "context_uid": "context",
        "context_name": "wiki",
        "checkpoint_uid": state.checkpoint_uid,
        "timestamp": state.timestamp,
        "description": "Updated shuttle",
        "state": state,
    }
    active = HistorySearchResult(**common, selectable=True)
    archived = HistorySearchResult(**common, selectable=False)

    from memcommit.commands.shared.history_present import (
        history_result_picker_entries,
    )

    entries = history_result_picker_entries([active, archived])

    assert "active checkpoint · restorable" in entries[0].detail
    assert "archived checkpoint · non-restorable" in entries[1].detail


def test_current_memory_version_projection_is_explicitly_uncheckpointed():
    version = MemoryVersion(
        context_uid="context",
        context_name="wiki",
        memory_uid="memory",
        content="Current unsaved notice.",
        content_digest="digest",
    )
    state = HistoryState(
        index=3,
        checkpoint_uid=None,
        timestamp=None,
        command="current",
        description="Current state",
        memories=(version,),
        record_digest="record",
        selectable=False,
        current=True,
    )
    result = HistorySearchResult(
        candidate_id="v000002",
        kind="memory_version",
        context_uid="context",
        context_name="wiki",
        checkpoint_uid=None,
        timestamp=None,
        description=version.content,
        selectable=False,
        state=state,
        memory_version=version,
    )

    from memcommit.commands.shared.history_present import (
        history_result_picker_entries,
    )

    entry = history_result_picker_entries([result])[0]

    assert "current-uncheckpointed Memory version" in entry.detail
    assert "non-restorable" in entry.detail


def test_restored_transition_labels_checkpoint_uid_as_operation_receipt():
    before = MemoryVersion(
        context_uid="context",
        context_name="wiki",
        memory_uid="memory",
        content="New notice.",
        content_digest="new",
    )
    after = MemoryVersion(
        context_uid="context",
        context_name="wiki",
        memory_uid="memory",
        content="Restored notice.",
        content_digest="restored",
    )
    transition = MemoryTransition(
        index=3,
        step_index=4,
        context_uid="context",
        context_name="wiki",
        checkpoint_uid="44444444-4444-4444-8444-444444444444",
        timestamp="2026-07-30T13:00:00",
        command="revert",
        description="Restored an earlier Context state",
        kind="RESTORED",
        evidence="RECORDED",
        memory_uid="memory",
        before=before,
        after=after,
        from_state_index=3,
        to_state_index=4,
    )
    result = HistorySearchResult(
        candidate_id="t000001",
        kind="memory_transition",
        context_uid="context",
        context_name="wiki",
        checkpoint_uid=transition.checkpoint_uid,
        timestamp=transition.timestamp,
        description="RESTORED · Restored notice.",
        selectable=False,
        transition=transition,
    )

    from memcommit.commands.shared.history_present import (
        history_result_picker_entries,
        history_result_recovery_label,
    )

    entry = history_result_picker_entries([result])[0]
    plain_label = history_result_recovery_label(result)

    assert (
        "Operation receipt: 44444444-4444-4444-8444-444444444444"
        in entry.detail
    )
    assert "Checkpoint:" not in entry.detail
    assert "event boundary · not a direct restore target" in entry.detail
    assert "operation receipt 44444444" in plain_label
