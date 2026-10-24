"""Resolve exact local Context targets within one captured Store."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.persistence.store import MemoryStore


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
