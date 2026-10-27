"""Prepare exact Branch-created Context trees for Undo or Redo."""

from __future__ import annotations

from typing import Literal


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
        branch_tree_receipt,
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

    from .context_creation import restore_created_contexts

    return restore_created_contexts(
        store,
        unit,
        direction,
        current_before=receipt.current_before,
        current_after=receipt.target_root,
    )
