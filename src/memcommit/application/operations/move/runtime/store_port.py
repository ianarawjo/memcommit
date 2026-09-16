"""MemoryStore entry point for the Move operation."""

from __future__ import annotations

from memcommit.application.operations.move.application import run_move
from memcommit.application.operations.move.contracts import (
    FrozenMoveMemoriesPlan,
    MoveMemoriesRequest,
    MoveMemoriesResult,
)
from memcommit.application.operations.move.runtime.apply import apply_move
from memcommit.application.operations.move.runtime.prepare import freeze_move
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore


class MemoryStoreMovePort:
    """Capture Move's command-start orientation and wire its prepare/apply implementations."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        current_name: str | None,
        allow_granted_sources: bool = False,
    ):
        if type(allow_granted_sources) is not bool:
            raise TypeError("allow_granted_sources must be a boolean.")
        self._store = store
        self._current_name = current_name
        # This compatibility flag enables Grant diagnosis, never granted Move.
        self._allow_granted_sources = allow_granted_sources
        self._owner = object()

    @classmethod
    def capture(
        cls, store: MemoryStore, *, allow_granted_sources: bool = False
    ) -> MemoryStoreMovePort:
        return cls(
            store,
            current_name=store.current_context_name(),
            allow_granted_sources=allow_granted_sources,
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

    def freeze_move(self, request: MoveMemoriesRequest) -> FrozenMoveMemoriesPlan:
        return freeze_move(
            request,
            store=self._store,
            current_name=self._current_name,
            owner=self._owner,
            allow_granted_sources=self._allow_granted_sources,
        )

    def apply_move(self, plan: FrozenMoveMemoriesPlan) -> MoveMemoriesResult:
        return apply_move(plan, store=self._store, owner=self._owner)


def execute_move(
    request: MoveMemoriesRequest, *, store: MemoryStore
) -> MoveMemoriesResult:
    return run_move(request, port=MemoryStoreMovePort.capture(store))
