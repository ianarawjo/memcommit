"""Restore one Sync lifecycle through the same frozen publication journal."""

from datetime import datetime

from memcommit.application.capabilities.command_recovery.model import (
    CommandRestoreResult,
)
from memcommit.application.operations.import_export_sync.mem_sync.model import (
    ProfileDocumentChanges,
    SyncContextChange,
    SyncPlan,
)
from memcommit.application.operations.import_export_sync.mem_sync.publication import (
    publish_profile_changes,
)
from memcommit.models.checkpoint import Checkpoint
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)


def restore_sync_command(store, unit, direction):
    project_root_dir = store.store_dir.parent
    records = {context.name: context.to_dict() for context in store.load_all_contexts()}
    by_uid = {record["uid"]: record for record in records.values()}
    archives = {}
    root = store.command_context_archives_dir
    if root.exists():
        for checkpoint_uid in store.list_command_context_archive_uids():
            archive, manifest, context, entries = store._load_command_context_archive(
                checkpoint_uid
            )
            archives[context.uid] = (manifest["checkpoint_uid"], context.to_dict())
    changes = []
    archive_sources = {}
    for original in unit.changes:
        expected = original.after if direction == "undo" else original.before
        target = original.before if direction == "undo" else original.after
        uid = (expected or target)["uid"]
        actual = by_uid.get(uid)
        if actual != expected:
            raise ConcurrentContextUpdateError(
                f"Context changed after the Sync selected for {direction}: {uid}"
            )
        if expected is None and target is not None:
            archived = archives.get(uid)
            if archived is None:
                raise ValueError("Sync restoration Context archive is unavailable.")
            if target["name"] in records:
                raise ConcurrentContextUpdateError(
                    "Sync restoration destination is occupied."
                )
            archive_sources[uid] = archived[0]
        action = (
            "ADD"
            if expected is None
            else "REMOVE"
            if target is None
            else "RENAME"
            if expected["name"] != target["name"]
            else "EDIT"
        )
        changes.append(SyncContextChange(expected, target, action, ()))
    profile = ProfileDocumentChanges(
        None,
        tuple(records.values()),
        tuple(changes),
        (),
        (),
    )
    plan = SyncPlan((), (), profile)
    restoration = {
        "source_unit_uid": unit.uid,
        "direction": direction,
        "archive_sources": archive_sources,
    }
    result = publish_profile_changes(
        store,
        project_root_dir,
        plan,
        restoration=restoration,
    )
    checkpoints = []
    for change, (_name, checkpoint_uid) in zip(
        changes, result.checkpoint_uids, strict=True
    ):
        if change.after is not None:
            entries = store.list_checkpoints(change.after["name"])
        else:
            _archive, _manifest, _context, entries = (
                store._load_command_context_archive(checkpoint_uid)
            )
        record = next(entry for entry in entries if entry["uid"] == checkpoint_uid)
        checkpoints.append(
            Checkpoint(
                **{
                    key: value
                    for key, value in record.items()
                    if key != "command_before" and key != "timestamp"
                },
                timestamp=datetime.fromisoformat(record["timestamp"]),
            )
        )
    return CommandRestoreResult(unit, direction, result.run_uid, tuple(checkpoints))
