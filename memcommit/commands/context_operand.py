"""Command-entry resolution for existing ordinary Context operands."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.context_locator import resolve_context_locator
from memcommit.store import MemoryStore


@dataclass(frozen=True)
class ContextOperandSnapshot:
    """One frozen active-Context base shared by an entire command invocation.

    This object deliberately resolves names only.  Existence, load authority,
    locks, and persistence remain operation-specific command responsibilities.
    """

    current_name: str | None

    @classmethod
    def capture(cls, store: MemoryStore) -> "ContextOperandSnapshot":
        """Read the active Context exactly once for this command invocation."""
        return cls(current_name=store.current_context_name())

    def resolve(self, locator: str) -> str:
        """Return the canonical name selected by one existing-Context operand."""
        return resolve_context_locator(locator, current=self.current_name)

    def resolve_or_current(self, locator: str | None) -> str | None:
        """Resolve an explicit operand or use the same frozen active name."""
        if locator is None:
            return self.current_name
        return self.resolve(locator)
