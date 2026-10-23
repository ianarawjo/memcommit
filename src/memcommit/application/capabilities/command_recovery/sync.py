"""Interpret retained Sync lifecycle receipts as common command history units."""

from uuid import UUID

from memcommit.application.capabilities.command_recovery.model import (
    CommandContextChange,
    CommandHistoryError,
    ContextCommandUnit,
)
from memcommit.persistence.operations.mem_sync.run_repository import SyncRunRepository
from memcommit.persistence.store.context_memory.records import canonical_context_record


def sync_command_events(store):
    # Imported at call time so the shared reconstruction model remains the
    # owner of event ordering, including ordinary non-Sync commands.
    from .stack_reconstruction import _StackEvent

    originals = []
    restorations = []
    for record in SyncRunRepository(store).profile_history():
        frame = record["profile"]
        if frame.get("version") not in {1, 2}:
            raise CommandHistoryError("Invalid Sync lifecycle history version.")
        restoration = frame.get("restoration")
        if restoration:
            if restoration.get("direction") not in {"undo", "redo"}:
                raise CommandHistoryError("Invalid Sync restoration direction.")
            restorations.append((record, restoration))
            continue
        changes = []
        for change in frame["changes"]:
            before = (
                canonical_context_record(change["before"])
                if change["before"] is not None
                else None
            )
            after = (
                canonical_context_record(change["after"])
                if change["after"] is not None
                else None
            )
            subject = after or before
            if subject is None or before and after and before["uid"] != after["uid"]:
                raise CommandHistoryError("Invalid Sync lifecycle Context identity.")
            uid = subject["uid"]
            checkpoint_uid = frame["checkpoint_uids"][uid]
            UUID(checkpoint_uid)
            changes.append(
                CommandContextChange(
                    uid, subject["name"], before, after, checkpoint_uid
                )
            )
        if not changes or len({change.context_uid for change in changes}) != len(
            changes
        ):
            raise CommandHistoryError("Invalid Sync lifecycle membership.")
        unit = ContextCommandUnit(
            "sync:" + record["uid"],
            "sync",
            "Sync project documents",
            frame["started_at"],
            frame["started_at"],
            tuple(changes),
            ({"sync_profile_uid": record["uid"]},),
        )
        originals.append(
            _StackEvent(unit.started_at, unit.completed_at, "original", unit.uid, unit)
        )
    units = {event.unit.uid: event.unit for event in originals}
    for record, restoration in restorations:
        unit = units.get(restoration.get("source_unit_uid"))
        if unit is None:
            raise CommandHistoryError(
                "Sync restoration has no retained source operation."
            )
        timestamp = record["profile"]["started_at"]
        originals.append(
            _StackEvent(
                timestamp, timestamp, restoration["direction"], record["uid"], unit
            )
        )
    return originals
