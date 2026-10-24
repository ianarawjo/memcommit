"""Prepare mixed existing/created Merge Contexts for Undo or Redo."""

from __future__ import annotations

import uuid

from memcommit.models.context import Context
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.context_memory.records import context_record_digest

from memcommit.persistence.store.saving.command_restoration.merge import (
    save_merge_undo,
    save_merge_redo,
)


def restore_merge_context_creation(store, unit, direction: str):
    """Atomically restore a Merge across updated and created Contexts.

    Created descendants move into the same private, validated lifecycle
    archive used by command history. Updated Contexts are restored in
    place. Every member receives the same restoration receipt, so neither
    a partial tree nor an incomplete redo can enter the global stack.
    """
    from memcommit.application.capabilities.command_recovery import (
        CommandRestoreResult,
        command_restore_metadata,
    )

    if (
        unit.command not in {"merge", "meld"}
        or not unit.changes
        or any(change.after is None for change in unit.changes)
        or not any(change.before is None for change in unit.changes)
    ):
        raise ValueError(
            "Merge lifecycle restoration requires one complete mixed command unit."
        )
    names = tuple(change.context_name for change in unit.changes)
    receipt_uid = str(uuid.uuid4())
    restore_metadata = command_restore_metadata(
        receipt_uid=receipt_uid,
        direction=direction,
        unit=unit,
    )
    created_changes = tuple(change for change in unit.changes if change.before is None)
    updated_changes = tuple(
        change for change in unit.changes if change.before is not None
    )

    with store._context_graph_lock(exclusive=True):
        with store._context_write_locks(names):
            if direction == "undo":
                current_by_name: dict[str, Context] = {}
                original_bytes: dict[str, bytes] = {}
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
                            "after the Merge selected for undo."
                        )
                    if change.before is None:
                        store._assert_context_deletion_allowed(current)
                    current_by_name[change.context_name] = current
                    original_bytes[change.context_name] = (
                        store.load_context_record_bytes(change.context_name)
                    )

                checkpoints = save_merge_undo(
                    store,
                    unit,
                    restore_metadata,
                    current_by_name,
                    original_bytes,
                    updated_changes,
                    created_changes,
                )
            else:
                current_by_name: dict[str, Context] = {}
                original_bytes: dict[str, bytes] = {}
                archives: dict[str, tuple[object, object, Context]] = {}
                for change in updated_changes:
                    assert change.before is not None
                    try:
                        current = store.load_direct(change.context_name)
                    except FileNotFoundError as error:
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' "
                            "no longer exists."
                        ) from error
                    if current.uid != change.context_uid or context_record_digest(
                        current
                    ) != context_record_digest(change.before):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' changed "
                            "after the Merge selected for redo."
                        )
                    current_by_name[change.context_name] = current
                    original_bytes[change.context_name] = (
                        store.load_context_record_bytes(change.context_name)
                    )
                for change in created_changes:
                    if store.context_exists(change.context_name):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' already exists."
                        )
                    archive, manifest, archived, _entries = (
                        store._load_command_context_archive(change.checkpoint_uid)
                    )
                    assert change.after is not None
                    if (
                        manifest.get("command") != unit.command
                        or manifest.get("unit_uid") != unit.uid
                        or archived.uid != change.context_uid
                        or archived.name != change.context_name
                        or context_record_digest(archived)
                        != context_record_digest(change.after)
                    ):
                        raise ConcurrentContextUpdateError(
                            "The archived Merge result changed before Redo."
                        )
                    archives[change.context_name] = (
                        archive,
                        manifest,
                        archived,
                    )

                checkpoints = save_merge_redo(
                    store,
                    unit,
                    restore_metadata,
                    current_by_name,
                    original_bytes,
                    updated_changes,
                    created_changes,
                    archives,
                )

    return CommandRestoreResult(
        unit=unit,
        direction=direction,
        receipt_uid=receipt_uid,
        checkpoints=tuple(checkpoints),
    )
