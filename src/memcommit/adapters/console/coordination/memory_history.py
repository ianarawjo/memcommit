"""Coordinate retained-history access for Log's Memory mode and Trace."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.models.context import Context
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
    reconstruct_memory_history,
)
from memcommit.persistence.store import ProfileStore


@dataclass(frozen=True)
class RetainedHistoryContext:
    """One locally owned Context frozen for retained-history inspection."""

    display_name: str
    context: Context


def load_retained_history_context(
    store: ProfileStore,
    *,
    context_locator: str | None,
    current_name: str | None,
) -> RetainedHistoryContext:
    """Resolve READ, then enforce the stronger owner-history boundary."""

    access = resolve_existing_context_access(
        store,
        context_locator,
        current_name=current_name,
    ).value
    return RetainedHistoryContext(
        display_name=access.access_name,
        context=store.load_direct(access.context_name),
    )


def build_memory_history(
    store: ProfileStore,
    target: RetainedHistoryContext,
    selector: str,
) -> MemoryHistory:
    """Project one exact current-or-historical Memory lineage."""

    return reconstruct_memory_history(store, target.context, selector)
