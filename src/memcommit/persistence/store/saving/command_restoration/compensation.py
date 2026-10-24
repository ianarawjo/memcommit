"""Reverse completed restoration changes after an ordinary execution failure.

This process-local stack is not a durable crash-recovery journal. Callers own
the locks, mutation policy, and the inverse of each operation-specific write.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path


class RestorationRollbackError(RuntimeError):
    """Restoration failed and at least one inverse could not be completed."""

    def __init__(self, failures: tuple[Exception, ...]):
        self.failures = failures
        super().__init__(
            "Command restoration failed and could not be fully rolled back: "
            + "; ".join(str(error) for error in failures)
        )


class CompensationStack:
    """Keep each completed change's inverse until the owning scope succeeds."""

    def __init__(self) -> None:
        self._inverses: list[Callable[[], object]] = []

    def defer(self, callback: Callable[..., object], *args, **kwargs) -> None:
        self._inverses.append(partial(callback, *args, **kwargs))

    def move(self, source: Path, destination: Path) -> None:
        source.rename(destination)
        # Register each rename immediately: a later move can fail independently.
        self.defer(destination.rename, source)

    def __enter__(self) -> CompensationStack:
        return self

    def __exit__(self, exc_type, error, traceback) -> bool:
        inverses, self._inverses = self._inverses, []
        if error is None:
            return False
        failures: list[Exception] = []
        for inverse in reversed(inverses):
            try:
                inverse()
            except Exception as failure:
                # One broken inverse must not prevent recovery of other records.
                failures.append(failure)
        if failures:
            raise RestorationRollbackError(tuple(failures)) from error
        return False
