"""Shared retained-history controller for Log's Memory mode and Trace."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.authority.access import resolve_context_access
from memcommit.context import Context
from memcommit.retained_history.provenance import TraceReport, build_trace
from memcommit.persistence.store import MemoryStore
from memcommit.authority.study_operation_policy import require_trace_access


@dataclass(frozen=True)
class RetainedHistoryContext:
    """One locally owned Context frozen for retained-history inspection."""

    display_name: str
    storage_name: str
    context: Context


def load_retained_history_context(
    store: MemoryStore,
    *,
    context_locator: str | None,
    current_name: str | None,
) -> RetainedHistoryContext:
    """Resolve READ, then enforce the stronger owner-history boundary."""

    access = resolve_context_access(
        store,
        context_locator,
        current_name=current_name,
        required_permission="READ",
    )
    # A Grant attachment authorizes current content projection, not the
    # authority Profile's checkpoints, command receipts, or saved analyses.
    require_trace_access(
        access.display_name,
        granted=access.is_granted,
        store_root=store.store_dir,
    )
    return RetainedHistoryContext(
        display_name=access.display_name,
        storage_name=access.context_name,
        context=store.load_direct(access.context_name),
    )


def load_retained_history_scope(
    store: MemoryStore,
    *,
    context_locator: str | None,
    current_name: str | None,
    include_descendants: bool,
) -> tuple[RetainedHistoryContext, ...]:
    """Freeze one locally owned exact or lexical-descendant history range."""

    if type(include_descendants) is not bool:
        raise TypeError("Retained-history descendant scope must be a boolean.")
    root = load_retained_history_context(
        store,
        context_locator=context_locator,
        current_name=current_name,
    )
    names = tuple(
        name
        for name in store.list_context_names()
        if name == root.storage_name
        or (include_descendants and name.startswith(root.storage_name + "/"))
    )
    # The root access check above rejects a granted authority view before this
    # local catalog is opened. Every descendant is therefore owned by the same
    # active store rather than inferred from a public Grant hierarchy.
    return tuple(
        RetainedHistoryContext(
            display_name=name,
            storage_name=name,
            context=store.load_direct(name),
        )
        for name in names
    )


def build_memory_history(
    store: MemoryStore,
    target: RetainedHistoryContext,
    selector: str,
) -> TraceReport:
    """Project one exact current-or-historical Memory lineage."""

    return build_trace(store, target.context, selector)
