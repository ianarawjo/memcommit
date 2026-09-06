"""Freeze one local Context's checkpoint frame before Revert approval."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.adapters.console.commands.revert.review import (
    RevertSelectionReceipt,
    revert_exact_command_review,
)
from memcommit.adapters.console.commands.revert.workbench import choose_revert_history
from memcommit.adapters.console.terminal.components.command_editor.model import (
    CommandReview,
)
from memcommit.adapters.console.terminal.components.history.checkpoint_diff import (
    checkpoint_revision_detail_renderer,
)
from memcommit.adapters.console.terminal.components.history.presentation import (
    checkpoint_picker_entries,
)
from memcommit.application.capabilities.checkpoint_catalog import (
    ResolvedCheckpointUnit,
    freeze_checkpoint_catalog,
)
from memcommit.persistence.store import (
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
)


@dataclass(frozen=True)
class ReviewedCheckpointSelection:
    """Exact mutation target and freshness evidence frozen before its review."""

    context_name: str
    context_uid: str
    context_digest: str
    history_digest: str
    checkpoint_uid: str
    keep_history: bool
    checkpoint_unit: ResolvedCheckpointUnit


def review_context_checkpoints(
    store: MemoryStore,
    *,
    context_name: str,
    keep_history: bool = True,
    title: str = "REVERT",
) -> ReviewedCheckpointSelection | None:
    """Review the command's canonical Context without opening a namespace picker."""

    # Retain the former browser's ordinary-local target boundary. An active
    # public name or readable Grant is not itself a restorable local Context.
    local_names = tuple(store.list_context_names())
    if not local_names:
        raise ValueError(f"No Context locations are available for {title}.")
    if context_name not in local_names:
        raise ValueError(f"Context '{context_name}' is not available for {title}.")
    context = store.load_direct(context_name)
    checkpoints = store.list_checkpoints(context_name)
    catalog = freeze_checkpoint_catalog(store)
    reviewed_units: dict[str, ResolvedCheckpointUnit] = {}

    def review(uid: str, keep: bool) -> CommandReview:
        unit = catalog.resolve(uid, context_name=context_name)
        reviewed_units[uid] = unit
        return revert_exact_command_review(
            context_name=context_name,
            checkpoint_uid=uid,
            keep_history=keep,
            affected_checkpoints=tuple(
                (member.context_name, member.checkpoint_uid) for member in unit.members
            ),
        )

    # Every retained version remains selectable, even when command identities
    # repeat. The current Context is already resolved by the command adapter.
    projected = {entry.uid: entry for entry in checkpoint_picker_entries(checkpoints)}
    result = choose_revert_history(
        [projected[checkpoint["uid"]] for checkpoint in checkpoints],
        context_name=context_name,
        initial_details_open=True,
        detail_renderer=(
            checkpoint_revision_detail_renderer(checkpoints) if checkpoints else None
        ),
        empty_message="No checkpoints for this Context yet.",
        back_navigation=False,
        keep_history=keep_history,
        title=title,
        revert_review_factory=review,
    )
    if not isinstance(result, RevertSelectionReceipt):
        return None
    unit = reviewed_units.get(result.checkpoint_uid)
    if unit is None:
        unit = catalog.resolve(result.checkpoint_uid, context_name=context_name)
    return ReviewedCheckpointSelection(
        context_name=context_name,
        context_uid=context.uid,
        context_digest=context_record_digest(context),
        history_digest=checkpoint_history_digest(checkpoints),
        checkpoint_uid=result.checkpoint_uid,
        keep_history=result.keep_history,
        checkpoint_unit=unit,
    )
