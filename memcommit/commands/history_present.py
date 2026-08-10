"""Host-owned presentation projections for checkpoint and semantic history."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from memcommit.commands.history_picker import HistoryPickerEntry
from memcommit.history_search import HistorySearchResult
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import source_object_label


_MEMORY_REF_LABEL = source_object_label(SourceForm.MEMORY_REF)
_QUERY_VIEW_LABEL = source_object_label(SourceForm.QUERY_VIEW)
_EMBEDDED_CONTEXT_LABEL = "embedded " + source_object_label(SourceForm.CONTEXT)


def history_result_recovery_label(result: HistorySearchResult) -> str:
    """Describe whether and how one semantic result can restore Context state."""
    checkpoint = result.checkpoint_uid
    checkpoint_short = checkpoint[:8] if checkpoint else None
    if result.kind == "checkpoint":
        if result.selectable:
            return "active checkpoint · restorable"
        return "archived checkpoint · non-restorable"
    if result.kind == "memory_version":
        if result.state is not None and result.state.current and checkpoint is None:
            return "current-uncheckpointed Memory version · non-restorable"
        if result.selectable and checkpoint_short is not None:
            return (
                "Memory version · restorable via checkpoint "
                f"{checkpoint_short}"
            )
        if checkpoint_short is not None:
            return (
                f"Memory version · archived checkpoint {checkpoint_short} "
                "· non-restorable"
            )
        return "uncheckpointed Memory version · non-restorable"

    transition = result.transition
    if (
        transition is not None
        and transition.kind == "RESTORED"
        and checkpoint_short is not None
    ):
        boundary = f"operation receipt {checkpoint_short}"
    elif checkpoint_short is not None:
        boundary = f"checkpoint boundary {checkpoint_short}"
    else:
        boundary = "uncheckpointed event boundary"
    return f"event boundary · {boundary} · not a direct restore target"


def _snapshot_items(snapshot: object) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(snapshot, dict):
        return {}, []
    raw_items = snapshot.get("memories")
    items = (
        {
            uid: value
            for uid, value in raw_items.items()
            if isinstance(uid, str) and isinstance(value, dict)
        }
        if isinstance(raw_items, dict)
        else {}
    )
    raw_order = snapshot.get("order")
    order = (
        [
            uid
            for uid in raw_order
            if isinstance(uid, str) and uid in items
        ]
        if isinstance(raw_order, list)
        else list(items)
    )
    for uid in items:
        if uid not in order:
            order.append(uid)
    return items, order


def _kind_counts(snapshot: object) -> dict[str, int]:
    items, _ = _snapshot_items(snapshot)
    counts = {
        "memory": 0,
        "memory_ref": 0,
        "query_context_ref": 0,
        "context_ref": 0,
    }
    for item in items.values():
        kind = item.get("type")
        if kind in counts:
            counts[kind] += 1
    return counts


def _transition_detail(before: object, after: object) -> str:
    before_items, before_order = _snapshot_items(before)
    after_items, after_order = _snapshot_items(after)
    before_uids = set(before_items)
    after_uids = set(after_items)
    common = before_uids & after_uids
    added = len(after_uids - before_uids)
    removed = len(before_uids - after_uids)
    edited = sum(
        before_items[uid] != after_items[uid]
        for uid in common
    )
    before_positions = {
        uid: index
        for index, uid in enumerate(before_order)
    }
    after_positions = {
        uid: index
        for index, uid in enumerate(after_order)
    }
    reordered = sum(
        before_positions.get(uid) != after_positions.get(uid)
        for uid in common
    )
    return (
        f"+{added} added · ~{edited} edited · "
        f"-{removed} removed · {reordered} reordered"
    )


def checkpoint_picker_entries(
    checkpoints: Sequence[Mapping[str, Any]],
    *,
    extra_detail_by_uid: Mapping[str, str] | None = None,
) -> list[HistoryPickerEntry]:
    """Project newest-first checkpoint records into safe picker entries."""
    ordered_oldest = sorted(
        checkpoints,
        key=lambda entry: (
            str(entry.get("timestamp", "")),
            str(entry.get("uid", "")),
        ),
    )
    previous_snapshot_by_uid: dict[str, object | None] = {}
    previous: object | None = None
    for checkpoint in ordered_oldest:
        uid = checkpoint.get("uid")
        if isinstance(uid, str):
            previous_snapshot_by_uid[uid] = previous
        previous = checkpoint.get("snapshot")

    result: list[HistoryPickerEntry] = []
    for checkpoint in checkpoints:
        uid = checkpoint.get("uid")
        timestamp = checkpoint.get("timestamp")
        if not isinstance(uid, str) or not uid:
            raise ValueError("Checkpoint history contains an invalid UID.")
        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError(
                f"Checkpoint [{uid[:8]}] contains an invalid timestamp."
            )
        command = checkpoint.get("command")
        if not isinstance(command, str) or not command:
            command = "checkpoint"
        description = (
            checkpoint.get("description")
            or checkpoint.get("message")
            or "(no description)"
        )
        if not isinstance(description, str):
            description = "(invalid description)"

        counts = _kind_counts(checkpoint.get("snapshot"))
        total = sum(counts.values())
        snapshot_line = (
            f"Snapshot: {total} direct items · "
            f"{counts['memory']} Memories · "
            f"{counts['memory_ref']} {_MEMORY_REF_LABEL}s · "
            f"{counts['query_context_ref']} {_QUERY_VIEW_LABEL}s · "
            f"{counts['context_ref']} {_EMBEDDED_CONTEXT_LABEL}s"
        )
        before = previous_snapshot_by_uid.get(uid)
        transition_line = (
            "Transition: baseline · no preceding recoverable checkpoint"
            if before is None
            else "Transition: "
            + _transition_detail(before, checkpoint.get("snapshot"))
        )
        detail = "\n".join(
            (
                snapshot_line,
                transition_line,
                "History status: active checkpoint · restorable",
            )
        )
        extra = (
            extra_detail_by_uid.get(uid)
            if extra_detail_by_uid is not None
            else None
        )
        if extra:
            detail = f"{detail}\n{extra}"
        result.append(
            HistoryPickerEntry(
                uid=uid,
                timestamp=timestamp,
                command=command,
                description=description,
                detail=detail,
            )
        )
    return result


def history_result_picker_entries(
    results: Sequence[HistorySearchResult],
) -> list[HistoryPickerEntry]:
    """Project locally resolved semantic-history results for inspection."""
    entries: list[HistoryPickerEntry] = []
    for result in results:
        timestamp = result.timestamp or "current (uncheckpointed)"
        checkpoint = result.checkpoint_uid or "(not checkpointed)"
        if result.kind == "checkpoint":
            uid = result.checkpoint_uid or result.candidate_id
            command = result.state.command if result.state is not None else "checkpoint"
            memory_count = (
                len(result.state.memories)
                if result.state is not None
                else 0
            )
            detail = "\n".join(
                (
                    f"Checkpoint: {checkpoint}",
                    f"Direct Memories: {memory_count}",
                    "History status: "
                    + history_result_recovery_label(result),
                )
            )
        elif result.kind == "memory_transition":
            transition = result.transition
            uid = result.candidate_id
            command = (
                transition.kind.lower()
                if transition is not None
                else "memory-transition"
            )
            before = (
                transition.before.content
                if transition is not None and transition.before is not None
                else "(absent)"
            )
            after = (
                transition.after.content
                if transition is not None and transition.after is not None
                else "(absent)"
            )
            boundary_line = (
                f"Operation receipt: {checkpoint}"
                if transition is not None and transition.kind == "RESTORED"
                else f"Checkpoint boundary: {checkpoint}"
            )
            detail = "\n".join(
                (
                    boundary_line,
                    f"Before: {before}",
                    f"After: {after}",
                    "History role: event boundary · "
                    "not a direct restore target",
                    "Changes in one checkpoint are simultaneous.",
                )
            )
        else:
            version = result.memory_version
            uid = result.candidate_id
            command = "memory-version"
            content = (
                version.content
                if version is not None
                else result.description
            )
            detail = "\n".join(
                (
                    f"Checkpoint occurrence: {checkpoint}",
                    f"Memory: {content}",
                    "History status: "
                    + history_result_recovery_label(result),
                )
            )
        entries.append(
            HistoryPickerEntry(
                uid=uid,
                timestamp=timestamp,
                command=command,
                description=(
                    f"{result.context_name} · {result.description}"
                ),
                detail=detail,
            )
        )
    return entries
