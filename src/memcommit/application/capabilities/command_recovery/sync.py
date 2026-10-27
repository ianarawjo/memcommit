"""Group native Sync changes and native-only restorations as command units."""

from memcommit.application.capabilities.command_recovery.model import (
    CommandContextChange,
    CommandHistoryError,
    ContextCommandUnit,
)
from memcommit.persistence.operations.mem_sync.checkpoints import (
    load_sync_checkpoint_records,
)
from memcommit.persistence.operations.mem_sync.run_repository import SyncRunRepository


def sync_command_events(store, *, deleted_checkpoint_uids=frozenset()):
    from .stack_reconstruction import _StackEvent

    receipts = SyncRunRepository(store).profile_history()
    if not receipts:
        return []
    retired_units = {
        record["profile"]["restoration"]["source_unit_uid"]
        if record["profile"].get("restoration")
        else "sync:" + record["uid"]
        for record in receipts
        if any(
            uid in deleted_checkpoint_uids for _name, uid in record["checkpoint_uids"]
        )
    }
    checkpoints = load_sync_checkpoint_records(store)
    events = []
    restorations = []
    for record in receipts:
        frame = record["profile"]
        restoration = frame.get("restoration")
        if restoration:
            if restoration["source_unit_uid"] in retired_units:
                continue
            restorations.append((record, restoration))
            continue
        if "sync:" + record["uid"] in retired_units:
            continue
        changes = []
        for _name, checkpoint_uid in record["checkpoint_uids"]:
            checkpoint = checkpoints.get(checkpoint_uid)
            if checkpoint is None:
                raise CommandHistoryError("Sync command checkpoint is unavailable.")
            action = checkpoint["command_details"]["sync_operation"]["action"]
            if action == "UNCHANGED":
                continue
            before = checkpoint.get("command_before")
            after = None if action == "REMOVE" else checkpoint["snapshot"]
            subject = after or before
            changes.append(
                CommandContextChange(
                    subject["uid"], subject["name"], before, after, checkpoint_uid
                )
            )
        if not changes:
            raise CommandHistoryError("Sync command has no native changes.")
        unit = ContextCommandUnit(
            "sync:" + record["uid"],
            "sync",
            "Sync project documents",
            frame["started_at"],
            frame["started_at"],
            tuple(changes),
            ({"sync_profile_uid": record["uid"]},),
        )
        events.append(
            _StackEvent(unit.started_at, unit.completed_at, "original", unit.uid, unit)
        )
    units = {event.unit.uid: event.unit for event in events}
    for record, restoration in restorations:
        unit = units.get(restoration["source_unit_uid"])
        if unit is None or restoration["direction"] not in {"undo", "redo"}:
            raise CommandHistoryError(
                "Sync restoration has no retained source operation."
            )
        timestamp = record["profile"]["started_at"]
        events.append(
            _StackEvent(
                timestamp, timestamp, restoration["direction"], record["uid"], unit
            )
        )
    return events
