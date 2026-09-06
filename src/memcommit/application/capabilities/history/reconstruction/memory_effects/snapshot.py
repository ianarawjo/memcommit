"""Project remaining direct snapshot differences with verified operation annotations."""

from __future__ import annotations

import hashlib
from typing import Any

from ...model.memory_event import MemoryHistoryEvent, MemoryHistoryEventKind
from ...verification.checkpoint import _checkpoint_fields
from ...verification.frame import _Frame, _ordered_states
from ...verification.model import MemoryHistoryEvidence
from ...verification.validators.add import verify_add_occurrences
from .model import EffectDerivation


def snapshot_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
    changed: set[str],
    meld_changes: dict[str, dict[str, Any]],
) -> EffectDerivation:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    events: list[MemoryHistoryEvent] = []
    warnings: list[str] = []
    for uid in sorted(changed, key=lambda item: after.memories[item].position):
        meld = meld_changes.get(uid)
        events.append(
            MemoryHistoryEvent(
                kind="EDITED",
                evidence=(
                    "RECORDED"
                    if (command == "edit" or meld is not None)
                    else "RECONSTRUCTED"
                ),
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[uid],),
                after=(after.memories[uid],),
                reason=meld["reason"] if meld is not None else None,
                reason_codes=(
                    ("MELD", "EDIT", meld["disposition"]) if meld is not None else ()
                ),
                operation_id=meld["session_uid"] if meld is not None else None,
                declared_frame=(meld["declared_frame"] if meld is not None else None),
                declared_frame_digest=(
                    hashlib.sha256(meld["declared_frame"].encode("utf-8")).hexdigest()
                    if meld is not None
                    else None
                ),
                uncertainty_reason=(
                    "Edited by an accepted directional Context meld."
                    if meld is not None
                    else None
                ),
                source_review_uid=meld["session_uid"] if meld is not None else None,
                source_review_digest=(
                    meld["change_set_digest"] if meld is not None else None
                ),
            )
        )

    occurrences, occurrence_warnings = (
        verify_add_occurrences(
            args=args, after=after, added=added, checkpoint_uid=checkpoint_uid
        )
        if command == "add"
        else ({}, [])
    )
    warnings.extend(occurrence_warnings)
    source_context = args.get("source_context")
    init_memory_uids = args.get("memory_uids")
    recorded_init_copy = (
        command == "init"
        and isinstance(source_context, dict)
        and isinstance(source_context.get("uid"), str)
        and isinstance(source_context.get("name"), str)
        and isinstance(init_memory_uids, list)
        and all(isinstance(uid, str) for uid in init_memory_uids)
        and len(init_memory_uids) == len(set(init_memory_uids))
        and set(init_memory_uids) == added
    )
    for uid in sorted(added, key=lambda item: after.memories[item].position):
        occurrence, occurrence_evidence = occurrences.get(uid, (None, None))
        meld = meld_changes.get(uid)
        event_kind: MemoryHistoryEventKind = (
            "MERGED_IN"
            if command == "merge"
            else ("MELDED" if meld is not None else "CREATED")
        )
        evidence: MemoryHistoryEvidence
        if meld is not None:
            evidence = "RECORDED"
        elif occurrence_evidence is not None:
            evidence = occurrence_evidence
        elif recorded_init_copy:
            evidence = "RECORDED"
        elif command in {"add", "merge", "integrate"}:
            evidence = "RECONSTRUCTED"
        else:
            evidence = "INFERRED"
        events.append(
            MemoryHistoryEvent(
                kind=event_kind,
                evidence=evidence,
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                after=(after.memories[uid],),
                reason=(
                    meld["reason"]
                    if meld is not None
                    else (
                        "Copied into this Context's source-based initial "
                        f"frame from '{source_context['name']}'."
                        if recorded_init_copy
                        else None
                    )
                ),
                reason_codes=(
                    ("MELD", "ADD", meld["disposition"])
                    if meld is not None and meld["mode"] == "DIRECTIONAL"
                    else ("MELD", meld["disposition"])
                    if meld is not None
                    else ()
                ),
                source_occurrence=occurrence,
                operation_id=meld["session_uid"] if meld is not None else None,
                declared_frame=(meld["declared_frame"] if meld is not None else None),
                declared_frame_digest=(
                    hashlib.sha256(meld["declared_frame"].encode("utf-8")).hexdigest()
                    if meld is not None
                    else None
                ),
                uncertainty_reason=(
                    (
                        "Added by an accepted directional Context meld."
                        if meld["mode"] == "DIRECTIONAL"
                        else "Created by an accepted symmetric Context meld."
                    )
                    if meld is not None
                    else None
                ),
                source_review_uid=meld["session_uid"] if meld is not None else None,
                source_review_digest=(
                    meld["change_set_digest"] if meld is not None else None
                ),
            )
        )

    for uid in sorted(removed, key=lambda item: before.memories[item].position):
        events.append(
            MemoryHistoryEvent(
                kind="REMOVED",
                evidence=(
                    "RECORDED" if command in {"remove", "clear"} else "RECONSTRUCTED"
                ),
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[uid],),
            )
        )
    if set(before.memories) == set(after.memories) and before.order != after.order:
        moved = {
            uid
            for uid in before.memories
            if before.memories[uid].position != after.memories[uid].position
        }
        if moved:
            events.append(
                MemoryHistoryEvent(
                    kind="REORDERED",
                    evidence="RECONSTRUCTED",
                    timestamp=timestamp,
                    checkpoint_uid=checkpoint_uid,
                    command=command,
                    description=description,
                    before=_ordered_states(before, moved),
                    after=_ordered_states(after, moved),
                    reason="Canonical direct Memory order changed.",
                )
            )
    return EffectDerivation(events=events, warnings=warnings)
