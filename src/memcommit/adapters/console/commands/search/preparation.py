"""Resolve Search operands into one frozen, grant-aware execution environment."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.context_access.access import ContextAccess
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
    freeze_profile_readable_context_catalog,
    freeze_readable_context_catalog,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class PreparedSearch:
    """Canonical targets and their exact access routes from one preparation."""

    current_name: str | None
    initial_access: ContextAccess
    target_names: tuple[str, ...]
    catalog: ReadableContextCatalog
    all_contexts: bool


def prepare_search(
    store: MemoryStore,
    *,
    context_names: Sequence[str] | str | None = None,
    all_contexts: bool = False,
    interactive: bool = False,
    follow_embeds: bool = False,
) -> PreparedSearch:
    snapshot = ContextOperandSnapshot.capture(store)
    if all_contexts and context_names:
        raise ValueError("--all/-a cannot be combined with --context/-c.")
    operands = (
        (context_names,)
        if isinstance(context_names, str)
        else tuple(context_names)
        if context_names
        else (None,)
    )
    candidates = freeze_profile_context_access_candidates(
        store,
        current_name=snapshot.current_name,
    )
    accesses = tuple(
        resolve_existing_context_access(
            store,
            operand,
            current_name=snapshot.current_name,
            required_permission="READ",
            candidates=candidates,
        ).value
        for operand in operands
    )
    target_names = tuple(access.access_name for access in accesses)
    if len(set(target_names)) != len(target_names):
        raise ValueError("Search Context roots must be distinct.")
    initial_access = accesses[0]
    # TUI Browse exposes PROFILE and can toggle Embeds later. A static exact
    # request retains its selected-Context catalog instead of gaining breadth.
    freeze_catalog = (
        freeze_profile_readable_context_catalog
        if interactive or all_contexts or len(target_names) > 1
        else freeze_readable_context_catalog
    )
    catalog = freeze_catalog(
        store,
        initial_access,
        include_query_routes=interactive or follow_embeds,
    )
    if all_contexts:
        # Expand PROFILE from the same catalog passed to execution and the TUI;
        # launching the workbench must not take a second namespace snapshot.
        target_names = tuple(catalog.list_context_names())
    for name in target_names:
        catalog.access_for(name)
    return PreparedSearch(
        snapshot.current_name,
        initial_access,
        target_names,
        catalog,
        all_contexts,
    )
