"""MemoryStore entry point for the Copy operation."""

from __future__ import annotations

from memcommit.application.operations.copy.application import run_copy
from memcommit.application.operations.copy.contracts import (
    CopyMemoriesRequest,
    CopyMemoriesResult,
    FrozenCopyMemoriesPlan,
)
from memcommit.application.operations.copy.runtime.apply import apply_copy
from memcommit.application.operations.copy.runtime.prepare import freeze_copy
from memcommit.models.context import Context
from memcommit.persistence.store import MemoryStore


class MemoryStoreCopyPort:
    """Capture Copy's command-start orientation and wire its prepare/apply implementations."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        current_name: str | None,
    ):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> MemoryStoreCopyPort:
        return cls(
            store,
            current_name=store.current_context_name(),
        )

    @property
    def local_context_names(self) -> tuple[str, ...]:
        return tuple(self._store.list_context_names())

    @property
    def store(self) -> MemoryStore:
        return self._store

    @property
    def current_context_name(self) -> str | None:
        return self._current_name

    def inspect_local_context(self, name: str) -> Context:
        return self._store.load_direct(name)

    def freeze_copy(self, request: CopyMemoriesRequest) -> FrozenCopyMemoriesPlan:
        return freeze_copy(
            request,
            store=self._store,
            current_name=self._current_name,
            owner=self._owner,
        )

    def apply_copy(self, plan: FrozenCopyMemoriesPlan) -> CopyMemoriesResult:
        return apply_copy(plan, store=self._store, owner=self._owner)


def execute_copy(
    request: CopyMemoriesRequest, *, store: MemoryStore
) -> CopyMemoriesResult:
    return run_copy(request, port=MemoryStoreCopyPort.capture(store))
