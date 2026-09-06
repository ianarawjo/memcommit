"""Run one blocking command stage behind the shared transient progress line."""

from __future__ import annotations

from collections.abc import Callable
import sys
from typing import Protocol, TypeVar

from memcommit.adapters.console.terminal.components.progress import (
    BUSY_INTERVAL_SECONDS,
    CommandProgress,
)


T = TypeVar("T")


class CommandWaitProgress(Protocol):
    """The real stage boundary exposed to one blocking operation."""

    def update(self, stage: str, *, step: int) -> None: ...


def run_command_wait(
    operation: str,
    stage: str,
    *,
    total: int,
    work: Callable[[CommandWaitProgress], T],
    step: int = 1,
    interactive: bool | None = None,
    interval: float = BUSY_INTERVAL_SECONDS,
) -> T:
    """Execute work once on the calling thread, preserving its result or error."""

    enabled = (
        sys.stdin.isatty() and sys.stdout.isatty()
        if interactive is None
        else interactive
    )
    # Preserve the existing stream contract: an interactive command forces the
    # line on; otherwise CommandProgress decides from its captured stderr TTY.
    with CommandProgress(
        operation,
        stage,
        total=total,
        step=step,
        enabled=True if enabled else None,
        interval=interval,
    ) as progress:
        return work(progress)
