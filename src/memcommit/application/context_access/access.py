"""Resolve exact local Context targets within one captured Store."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.persistence.store import MemoryStore
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
)


@dataclass(frozen=True)
class ContextAccess:
    """One local Context name bound to the Store captured by its operation."""

    store: MemoryStore
    context_name: str
    access_name: str


def resolve_context_access(
    active_store: MemoryStore,
    operand: str | None,
    *,
    current_name: str | None,
) -> ContextAccess:
    """Resolve an existing local Context against the command-start selection."""
    if operand is None:
        if not current_name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        operand = current_name
    name = resolve_context_locator(operand, current=current_name)
    if not active_store.context_exists(name):
        raise FileNotFoundError(f"Context '{name}' does not exist.")
    return ContextAccess(active_store, name, name)


def revalidate_context_access(access: ContextAccess) -> None:
    """Check target existence without changing an operation's captured Store."""
    if not access.store.context_exists(access.context_name):
        raise FileNotFoundError(f"Context '{access.context_name}' does not exist.")


def context_access_display_facts(
    access: ContextAccess,
    *,
    reach: SourceReach = SourceReach.DIRECT,
    form: SourceForm = SourceForm.CONTEXT,
    states: tuple[SourceState, ...] = (),
) -> SourceDisplayFacts:
    """Project the local target's reach and item kind for shared presentation."""
    return SourceDisplayFacts(reach=reach, form=form, states=states)
