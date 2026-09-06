"""Coordinate evidence precedence and exactly which deltas remain unexplained."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ...model.memory_event import MemoryHistoryEvent
from ...verification.checkpoint import _checkpoint_fields
from ...verification.frame import _Frame
from ...verification.model import MemoryHistoryCommandOperation
from ...verification.validators.atomize import (
    _atomize_save_as_source_frame,
    verify_atomize_changes,
)
from ...verification.validators.chunk import verify_context_chunk, verify_legacy_chunk
from ...verification.validators.command_operation import _update_command_operation
from ...verification.validators.meld import _meld_change_evidence
from ...verification.validators.translate import verify_translation
from ..memory_state_delta import direct_memory_deltas
from .recorded import (
    atomize_baseline_events,
    atomize_events,
    chunk_events,
    restoration_events,
    translation_events,
)
from .snapshot import snapshot_events


def _transition_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    restoration: MemoryHistoryCommandOperation | bool = False,
) -> tuple[list[MemoryHistoryEvent], list[str]]:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    deltas = direct_memory_deltas(
        before.memories,
        after.memories,
        before_order=before.order,
        after_order=after.order,
        content=lambda state: state.content,
    )
    removed = {delta.memory_uid for delta in deltas if delta.kind == "REMOVED"}
    added = {delta.memory_uid for delta in deltas if delta.kind == "CREATED"}
    changed = {delta.memory_uid for delta in deltas if delta.kind == "EDITED"}

    if restoration:
        return restoration_events(
            before=before,
            after=after,
            entry=entry,
            affected=removed | added | changed,
            restoration=restoration,
        ), []

    trace_before = (
        _atomize_save_as_source_frame(args, after) if command == "atomize" else None
    )
    changes, warnings = verify_atomize_changes(
        before=trace_before or before, after=after, entry=entry
    )
    explicit = atomize_events(
        changes, before=trace_before or before, after=after, entry=entry
    )
    events = explicit.events
    if trace_before is not None:
        events = (
            atomize_baseline_events(trace_before=trace_before, entry=entry) + events
        )
    command_operation = _update_command_operation(
        command=command,
        args=args,
        context_uid=after.context_uid,
        context_name=after.context_name,
    )
    if (
        command == "update"
        and any(
            key in args
            for key in (
                "update_session_uid",
                "operation_digest",
                "command_contexts",
            )
        )
        and command_operation is None
    ):
        warnings.append(
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Update command-unit "
            "metadata; its changes cannot be correlated across Contexts."
        )
    # Recorded relations consume deltas before generic projection, preventing
    # SPLIT/TRANSLATED results from also appearing as independent add/remove events.
    removed -= explicit.consumed_before
    added -= explicit.consumed_after
    changed -= explicit.consumed_before | explicit.consumed_after

    meld_changes: dict[str, dict[str, Any]] = {}
    if command == "meld":
        meld_changes, meld_error = _meld_change_evidence(
            args=args,
            before=before,
            after=after,
        )
        if meld_error is not None:
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] {meld_error}; "
                "its results were reconstructed from snapshots."
            )

    translation, translation_warnings = verify_translation(
        before=before,
        after=after,
        entry=entry,
        removed=removed,
        added=added,
        changed=changed,
    )
    warnings.extend(translation_warnings)
    if translation is not None:
        projected = translation_events(
            translation, before=before, after=after, entry=entry
        )
        events.extend(projected.events)
        removed -= projected.consumed_before
        added -= projected.consumed_after

    chunk = verify_context_chunk(
        before=before, after=after, entry=entry, removed=removed, added=added
    )
    if chunk is None:
        chunk = verify_legacy_chunk(
            before=before, after=after, entry=entry, removed=removed, added=added
        )
    if chunk is not None:
        projected = chunk_events(chunk, before=before, after=after, entry=entry)
        events.extend(projected.events)
        removed -= projected.consumed_before
        added -= projected.consumed_after
    elif command == "chunk" and (removed or added):
        warnings.append(
            f"Checkpoint [{checkpoint_uid[:8]}] is a legacy chunk whose "
            "parent-child mapping could not be reconstructed safely."
        )

    snapshot = snapshot_events(
        before=before,
        after=after,
        entry=entry,
        removed=removed,
        added=added,
        changed=changed,
        meld_changes=meld_changes,
    )
    events.extend(snapshot.events)
    warnings.extend(snapshot.warnings)
    if command_operation is not None:
        events = [
            replace(
                event,
                operation_id=event.operation_id or command_operation.uid,
                command_operation=command_operation,
            )
            for event in events
        ]
    return events, warnings
