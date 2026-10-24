"""Prepare exact Branch-created Context trees for Undo or Redo."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from memcommit.models.context import Context
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.context_memory.records import context_record_digest

from memcommit.persistence.store.saving.command_restoration.branch import (
    save_branch_undo,
    save_branch_redo,
)


def restore_branch_context_creation(
    store,
    unit,
    direction: Literal["undo", "redo"],
):
    """Undo or redo one exact Branch or complete lexical subtree.

    Undo moves the created Context records and their inherited histories
    into private command archives. Redo restores those exact identities;
    it must not synthesize a fresh Branch from a Source that may have
    changed since the original command.
    """

    from memcommit.application.capabilities.command_recovery import (
        CommandHistoryError,
        CommandRestoreResult,
        branch_tree_receipt,
        command_restore_metadata,
    )

    if (
        unit.command != "branch"
        or not unit.changes
        or any(
            change.before is not None or change.after is None for change in unit.changes
        )
        or not unit.checkpoint_command_details
    ):
        raise ValueError(
            "Branch lifecycle restoration requires one complete creation unit."
        )
    try:
        receipts = tuple(
            branch_tree_receipt(args) for args in unit.checkpoint_command_details
        )
    except CommandHistoryError as error:
        raise ValueError(str(error)) from error
    receipt = receipts[0]
    if (
        any(candidate != receipt for candidate in receipts[1:])
        or unit.uid != f"branch:{receipt.operation_uid}"
        or {(change.context_uid, change.context_name) for change in unit.changes}
        != {(item.target_uid, item.target_name) for item in receipt.contexts}
    ):
        raise ValueError("Branch lifecycle receipts are inconsistent.")

    names = tuple(change.context_name for change in unit.changes)
    receipt_uid = str(uuid.uuid4())
    restore_metadata = command_restore_metadata(
        receipt_uid=receipt_uid,
        direction=direction,
        unit=unit,
    )

    with store._context_graph_lock(exclusive=True):
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
                    store._assert_context_deletion_allowed(current)
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
                        "A Branch command archive already exists."
                    )

                checkpoints = save_branch_undo(
                    store, unit, restore_metadata, current_by_name, archives, receipt
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
                        archive_manifest.get("command") != "branch"
                        or archive_manifest.get("unit_uid") != unit.uid
                        or archived_record.uid != change.context_uid
                        or archived_record.name != change.context_name
                        or context_record_digest(archived_record)
                        != context_record_digest(change.after)
                    ):
                        raise ConcurrentContextUpdateError(
                            "The archived Branch result changed before Redo."
                        )
                    store._assert_context_storage_available(change.context_name)
                    archived[change.context_name] = (
                        archive_path,
                        archive_manifest,
                        archived_record,
                    )

                checkpoints = save_branch_redo(
                    store, unit, restore_metadata, archived, receipt
                )

    return CommandRestoreResult(
        unit=unit,
        direction=direction,
        receipt_uid=receipt_uid,
        checkpoints=tuple(checkpoints),
    )
