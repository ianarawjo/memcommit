"""MemoryStore adapter for the Move operation."""

from __future__ import annotations

from memcommit.application.operations.copy_and_move.application import (
    MoveMemoriesRequest,
    MoveMemoriesResult,
)
from memcommit.application.operations.copy_and_move.runtime import (
    MemoryStoreCopyAndMovePort,
)
from memcommit.application.operations.direct_changes.move.application import run_move
from memcommit.persistence.store import MemoryStore


class MemoryStoreMovePort(MemoryStoreCopyAndMovePort):
    """Move-specific Store port backed by the shared Copy/Move graph kernel."""


def execute_move(
    request: MoveMemoriesRequest,
    *,
    store: MemoryStore,
) -> MoveMemoriesResult:
    return run_move(request, port=MemoryStoreMovePort.capture(store))


__all__ = ["MemoryStoreMovePort", "execute_move"]
