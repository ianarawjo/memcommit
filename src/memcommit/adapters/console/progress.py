"""Operation-neutral progress feedback for blocking console work.

The provider boundary is often one indivisible call, so this module reports
honest host-owned stages and elapsed time rather than inventing a percentage.
Progress is transient and TTY-only: stable stdout, redirected stderr, and
machine-readable command output remain unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import sys
import threading
import time
from types import TracebackType
from typing import TextIO, TypeVar

from memcommit.adapters.console.text import display_escape_text
from memcommit.adapters.console.tui.core.activity import (
    BUSY_FRAMES as BUSY_FRAMES,
    BUSY_INTERVAL_SECONDS,
    busy_suffix,
)


ProviderT = TypeVar("ProviderT")


def render_progress_line(
    operation: str,
    stage: str,
    *,
    step: int,
    total: int,
    elapsed_seconds: float,
    frame_index: int,
) -> str:
    """Render one safe, single-line snapshot of known command progress."""
    if not operation.strip() or not stage.strip():
        raise ValueError("Progress operation and stage must be nonblank.")
    if total < 1 or not 1 <= step <= total:
        raise ValueError("Progress step must be within the declared total.")
    elapsed = max(0, int(elapsed_seconds))
    return (
        f"MEM {display_escape_text(operation.upper())} · {step}/{total} · "
        f"{display_escape_text(stage.upper())} {busy_suffix(frame_index)} · "
        f"{elapsed}s"
    )


class CommandProgress:
    """Animate one transient status line while synchronous work blocks.

    Callers update only at real orchestration boundaries. The animation and
    elapsed clock prove liveness within a boundary without claiming insight
    into provider-side completion.
    """

    def __init__(
        self,
        operation: str,
        stage: str,
        *,
        total: int,
        step: int = 1,
        stream: TextIO | None = None,
        enabled: bool | None = None,
        interval: float = BUSY_INTERVAL_SECONDS,
    ) -> None:
        if interval <= 0:
            raise ValueError("Progress interval must be positive.")
        # Capture stderr once so Click/Typer redirection and tests retain the
        # same output boundary for the lifetime of the status line.
        self._stream = stream if stream is not None else sys.stderr
        is_tty = bool(getattr(self._stream, "isatty", lambda: False)())
        self._enabled = is_tty if enabled is None else enabled
        self._operation = operation
        self._stage = stage
        self._step = step
        self._total = total
        self._interval = interval
        self._started_at = time.monotonic()
        self._frame_index = 0
        self._rendered_width = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False
        self._closed = False
        # Validate eagerly even when rendering is disabled.
        render_progress_line(
            operation,
            stage,
            step=step,
            total=total,
            elapsed_seconds=0,
            frame_index=0,
        )

    def __enter__(self) -> CommandProgress:
        self.start()
        return self

    def start(self) -> None:
        """Begin rendering once, allowing provider factories to start lazily."""
        if self._closed:
            raise RuntimeError("Closed command progress cannot be restarted.")
        if self._started:
            return
        self._started = True
        if not self._enabled:
            return
        self._render()
        self._thread = threading.Thread(
            target=self._animate,
            name="mem-command-progress",
            daemon=True,
        )
        self._thread.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    def update(self, stage: str, *, step: int) -> None:
        """Publish a real host-side stage transition immediately."""
        render_progress_line(
            self._operation,
            stage,
            step=step,
            total=self._total,
            elapsed_seconds=0,
            frame_index=0,
        )
        with self._lock:
            self._stage = stage
            self._step = step
            self._frame_index = 0
            if self._enabled:
                self._render_locked()

    def close(self) -> None:
        """Stop repainting and remove the transient line."""
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self._interval * 2))
            self._thread = None
        if not self._enabled or not self._started:
            return
        with self._lock:
            self._stream.write("\r" + (" " * self._rendered_width) + "\r")
            self._stream.flush()
            self._rendered_width = 0

    def _animate(self) -> None:
        while not self._stop.wait(self._interval):
            with self._lock:
                self._frame_index += 1
                self._render_locked()

    def _render(self) -> None:
        with self._lock:
            self._render_locked()

    def _render_locked(self) -> None:
        line = render_progress_line(
            self._operation,
            self._stage,
            step=self._step,
            total=self._total,
            elapsed_seconds=time.monotonic() - self._started_at,
            frame_index=self._frame_index,
        )
        padding = " " * max(0, self._rendered_width - len(line))
        self._stream.write("\r" + line + padding)
        self._stream.flush()
        self._rendered_width = len(line)


@contextmanager
def progressing_provider_factory(
    operation: str,
    completion_stage: str,
    provider_factory: Callable[[], ProviderT],
    *,
    connection_stage: str = "connecting provider",
) -> Iterator[Callable[[], ProviderT]]:
    """Wrap a lazy provider factory in one honest two-stage status line.

    Some command workflows decide inside a reusable domain helper whether a
    saved result can be reused. Starting only when that helper actually asks
    for a provider prevents a cache hit from briefly claiming semantic work.
    The caller-owned context keeps the line alive until the whole provider
    operation returns, while the wrapped factory advances the stage only
    after connection succeeds.
    """
    progress = CommandProgress(
        operation,
        connection_stage,
        total=2,
    )

    def connect() -> ProviderT:
        progress.start()
        provider = provider_factory()
        progress.update(completion_stage, step=2)
        return provider

    try:
        yield connect
    finally:
        progress.close()


__all__ = [
    "BUSY_FRAMES",
    "BUSY_INTERVAL_SECONDS",
    "CommandProgress",
    "busy_suffix",
    "progressing_provider_factory",
    "render_progress_line",
]
