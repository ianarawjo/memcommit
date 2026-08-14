"""MemoryStore infrastructure adapter for current Context orientation."""

from __future__ import annotations

from memcommit.current_context_application import (
    CurrentContextResult,
    get_current_context,
)
from memcommit.store import MemoryStore


class MemoryStoreCurrentContextReader:
    """Read navigation state without creating or loading Store contents."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def current_context_name(self) -> str | None:
        # A read-only orientation check must not initialize ~/.mem merely to
        # explain that no current Context exists.
        if not self._store.state_file.is_file():
            return None
        return self._store.current_context_name()


def read_current_context(store: MemoryStore) -> CurrentContextResult:
    """Execute the current-Context use case against one explicit Store."""

    return get_current_context(MemoryStoreCurrentContextReader(store))
