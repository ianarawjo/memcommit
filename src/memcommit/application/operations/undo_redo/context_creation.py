"""Restore complete Context creation batches without changing their identities."""

from __future__ import annotations

import uuid
from pathlib import Path

from memcommit.models.context import Context
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.context_memory.records import context_record_digest

from memcommit.persistence.store.saving.command_restoration.context_creation import (
    save_context_creation_undo,
    save_context_creation_redo,
)


def restore_context_creation_batch(store, unit, direction):
    receipts = tuple(
        details.get("context_creation_batch")
        for details in unit.checkpoint_command_details
    )
    receipt_record = receipts[0]
    membership = {(change.context_uid, change.context_name) for change in unit.changes}
    if (
        not isinstance(receipt_record, dict)
        or any(record != receipt_record for record in receipts)
        or membership
        != {(item["uid"], item["name"]) for item in receipt_record["contexts"]}
        or any(
            change.before is not None or change.after is None for change in unit.changes
        )
    ):
        raise ValueError("Context creation batch is inconsistent.")
    current_before = receipt_record["current_before"]
    current_after = receipt_record["current_after"]
    if unit.command == "atomize":
        details = unit.checkpoint_command_details[0]
        current_before = details["atomize_save_as"]["current_before"]
        current_after = details["context_creation"]["context_name"]
    return restore_created_contexts(
        store,
        unit,
        direction,
        current_before=current_before,
        current_after=current_after,
    )


def restore_created_contexts(store, unit, direction, *, current_before, current_after):
    from memcommit.application.capabilities.command_recovery import (
        CommandRestoreResult,
        command_restore_metadata,
    )
    from memcommit.persistence.store.context_hierarchy import validate_context_hierarchy

    from .context_creation_companions import prepare_creation_companion_changes

    names = tuple(change.context_name for change in unit.changes)
    receipt_uid = str(uuid.uuid4())
    restore_metadata = command_restore_metadata(
        receipt_uid=receipt_uid,
        direction=direction,
        unit=unit,
    )

    with store._context_graph_lock(exclusive=True):
        live_names = set(store.list_context_names())
        validate_context_hierarchy(
            live_names.difference(names)
            if direction == "undo"
            else live_names.union(names)
        )
        with store._context_write_locks(names):
            if direction == "undo":
                current_by_name: dict[str, Context] = {}
                for change in unit.changes:
                    try:
                        current = store.load_direct(change.context_name)
                    except FileNotFoundError as error:
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' "
                            "no longer exists."
                        ) from error
                    assert change.after is not None
                    if current.uid != change.context_uid or context_record_digest(
                        current
                    ) != context_record_digest(change.after):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' changed "
                            "after the Branch selected for undo."
                        )
                    current_by_name[change.context_name] = current

                archives = {
                    change.context_name: store._command_context_archive_path(
                        change.checkpoint_uid
                    )
                    for change in unit.changes
                }
                if any(
                    archive.exists() or archive.is_symlink()
                    for archive in archives.values()
                ):
                    raise ConcurrentContextUpdateError(
                        "A Context creation archive already exists."
                    )

                companions = prepare_creation_companion_changes(
                    store,
                    unit,
                    direction,
                    archives[names[0]],
                )
                checkpoints = save_context_creation_undo(
                    store,
                    unit,
                    restore_metadata,
                    current_by_name,
                    archives,
                    current_before=current_before,
                    companion_changes=companions,
                )
            else:
                archived: dict[
                    str,
                    tuple[Path, dict[str, object], Context],
                ] = {}
                for change in unit.changes:
                    if store.context_exists(change.context_name):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' already exists."
                        )
                    archive_path, archive_manifest, archived_record, _entries = (
                        store._load_command_context_archive(change.checkpoint_uid)
                    )
                    assert change.after is not None
                    if (
                        archive_manifest.get("command") != unit.command
                        or archive_manifest.get("unit_uid") != unit.uid
                        or archived_record.uid != change.context_uid
                        or archived_record.name != change.context_name
                        or context_record_digest(archived_record)
                        != context_record_digest(change.after)
                    ):
                        raise ConcurrentContextUpdateError(
                            "The archived Context creation result changed before Redo."
                        )
                    store._assert_context_storage_available(change.context_name)
                    archived[change.context_name] = (
                        archive_path,
                        archive_manifest,
                        archived_record,
                    )

                companions = prepare_creation_companion_changes(
                    store,
                    unit,
                    direction,
                    archived[names[0]][0],
                )
                checkpoints = save_context_creation_redo(
                    store,
                    unit,
                    restore_metadata,
                    archived,
                    current_before=current_before,
                    current_after=current_after,
                    companion_changes=companions,
                )

    return CommandRestoreResult(
        unit=unit,
        direction=direction,
        receipt_uid=receipt_uid,
        checkpoints=tuple(checkpoints),
    )
