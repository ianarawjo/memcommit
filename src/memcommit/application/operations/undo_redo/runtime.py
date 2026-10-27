"""Select and restore one global command unit for Undo or Redo."""

from memcommit.application.capabilities.command_recovery.model import (
    CommandHistoryError,
    CommandRestoreResult,
    RestoreDirection,
)
from memcommit.application.capabilities.command_recovery.stack_reconstruction import (
    build_command_stacks,
)
from memcommit.persistence.store import ProfileStore
from .context_records import restore_existing_contexts


def execute_undo(store: ProfileStore) -> CommandRestoreResult:
    return restore_context_command(store, "undo")


def execute_redo(store: ProfileStore) -> CommandRestoreResult:
    return restore_context_command(store, "redo")


def restore_context_command(
    store: ProfileStore, direction: RestoreDirection
) -> CommandRestoreResult:
    if direction not in {"undo", "redo"}:
        raise ValueError("Command restoration direction must be undo or redo.")
    stacks = build_command_stacks(store)
    candidates = stacks.undo if direction == "undo" else stacks.redo
    if not candidates:
        raise CommandHistoryError(
            f"There is no recorded Context command to {direction}."
        )
    unit = candidates[-1]
    from memcommit.persistence.store.context_hierarchy import validate_context_hierarchy

    final_names = set(store.list_context_names())
    for change in unit.changes:
        final_names.discard(change.context_name)
        target = change.before if direction == "undo" else change.after
        if target is not None:
            final_names.add(target["name"])
    validate_context_hierarchy(final_names)
    if unit.command == "sync" and any(
        "sync_profile_uid" in details for details in unit.checkpoint_command_details
    ):
        from .sync import restore_sync_command

        return restore_sync_command(store, unit, direction)
    if any(change.before is None or change.after is None for change in unit.changes):
        return restore_context_creation(store, unit, direction)
    return restore_existing_contexts(store, unit, direction)


def restore_context_creation(store, unit, direction):
    if any(
        "context_creation_batch" in details
        for details in unit.checkpoint_command_details
    ):
        from .context_creation import restore_context_creation_batch

        return restore_context_creation_batch(store, unit, direction)
    if unit.command == "branch":
        from .branch import restore_branch_context_creation

        return restore_branch_context_creation(store, unit, direction)
    if unit.command in {"merge", "meld"}:
        from .merge import restore_merge_context_creation

        return restore_merge_context_creation(store, unit, direction)
    if unit.command == "sever":
        from .sever import restore_sever_context_creation

        return restore_sever_context_creation(store, unit, direction)
    if unit.command == "atomize":
        from .atomize.restoration import restore_atomize_context_creation

        return restore_atomize_context_creation(store, unit, direction)
    raise ValueError(f"Command '{unit.command}' has no Context-creation restoration.")
