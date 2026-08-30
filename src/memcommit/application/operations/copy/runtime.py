"""MemoryStore adapter for the Copy operation."""

from __future__ import annotations

from memcommit.application.operations.copy.application import run_copy
from memcommit.application.operations.copy_and_move.application import (
    CopyMemoriesRequest,
    CopyMemoriesResult,
)
from memcommit.application.operations.copy_and_move.runtime import (
    MemoryStoreCopyAndMovePort,
)
from memcommit.persistence.store import MemoryStore


class MemoryStoreCopyPort(MemoryStoreCopyAndMovePort):
    """Copy-specific Store port backed by the shared Copy/Move graph kernel."""


def execute_copy(
    request: CopyMemoriesRequest,
    *,
    store: MemoryStore,
) -> CopyMemoriesResult:
    return run_copy(request, port=MemoryStoreCopyPort.capture(store))


__all__ = ["MemoryStoreCopyPort", "execute_copy"]

