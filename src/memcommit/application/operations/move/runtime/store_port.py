"""ProfileStore entry point for the Move operation."""

from __future__ import annotations

from memcommit.application.operations.move.application import run_move
from memcommit.application.operations.move.contracts import (
    FrozenMoveMemoriesPlan,
    MoveMemoriesRequest,
    MoveMemoriesResult,
)
from memcommit.application.operations.move.runtime.apply import apply_move
from memcommit.application.operations.move.runtime.prepare import freeze_move
from memcommit.models.context import Context
from memcommit.persistence.store import ProfileStore


class MemoryStoreMovePort:
    """Capture Move's command-start orientation and wire its prepare/apply implementations."""

    def __init__(
        self,
        store: ProfileStore,
        *,
        current_name: str | None,
    ):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: ProfileStore) -> MemoryStoreMovePort:
        return cls(
            store,
            current_name=store.current_context_name(),
        )

    @property
    def local_context_names(self) -> tuple[str, ...]:
        return tuple(self._store.list_context_names())

    @property
    def store(self) -> ProfileStore:
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
        )

    def apply_move(self, plan: FrozenMoveMemoriesPlan) -> MoveMemoriesResult:
        return apply_move(plan, store=self._store, owner=self._owner)


def execute_move(
    request: MoveMemoriesRequest, *, store: ProfileStore
) -> MoveMemoriesResult:
    return run_move(request, port=MemoryStoreMovePort.capture(store))
