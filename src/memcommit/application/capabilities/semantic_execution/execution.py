"""Atomic orchestration mechanics for already-planned semantic batches."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from memcommit.application.capabilities.semantic_execution.coverage import InputCoverageLedger


T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class ExecutionProgress:
    """Operation-neutral progress suitable for a CLI or TUI projection."""

    phase: str
    batch_index: int
    batch_count: int

    def __post_init__(self) -> None:
        if self.phase not in {"BATCH", "RECONCILE", "COMPLETE"}:
            raise ValueError("Unknown semantic execution progress phase.")
        if self.batch_count < 1 or not 0 <= self.batch_index <= self.batch_count:
            raise ValueError("Invalid semantic execution progress position.")


def run_partitioned(
    batches: Sequence[tuple[T, ...]],
    *,
    item_id: Callable[[T], str],
    execute: Callable[[tuple[T, ...], int, int], R],
    on_progress: Callable[[ExecutionProgress], None] | None = None,
) -> tuple[R, ...]:
    """Execute all batches and return results only after exact input coverage.

    The ledger is process-local and records a batch only after its provider call
    succeeds. An exception therefore exposes no partial result to the caller.
    """

    frozen_batches = tuple(tuple(batch) for batch in batches)
    if not frozen_batches or any(not batch for batch in frozen_batches):
        raise ValueError("Partitioned semantic execution requires nonempty batches.")
    expected_ids = tuple(item_id(item) for batch in frozen_batches for item in batch)
    ledger = InputCoverageLedger(expected_ids)
    results: list[R] = []
    total = len(frozen_batches)
    for index, batch in enumerate(frozen_batches, start=1):
        if on_progress is not None:
            on_progress(ExecutionProgress("BATCH", index, total))
        result = execute(batch, index, total)
        ledger.record(tuple(item_id(item) for item in batch))
        results.append(result)
    ledger.finalize()
    if on_progress is not None:
        on_progress(ExecutionProgress("COMPLETE", total, total))
    return tuple(results)
