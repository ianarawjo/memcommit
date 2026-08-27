"""Shared close-safe lifecycle for blocking workbench controller turns."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextvars import copy_context
from typing import Generic, TypeVar

from memcommit.adapters.interfaces.tui.core.activity import BUSY_INTERVAL_SECONDS


T = TypeVar("T")


class BackgroundExecutorTurn(Generic[T]):
    """Run one non-cancellable blocking turn without freezing prompt-toolkit.

    The operation supplies meaning, validation, and commit callbacks. This
    controller owns only mutual exclusion, animation, executor shutdown, and
    the deliberate close-after-turn boundary.
    """

    def __init__(self, *, interval_seconds: float = BUSY_INTERVAL_SECONDS) -> None:
        if interval_seconds <= 0:
            raise ValueError("Background turn interval must be positive.")
        self.interval_seconds = interval_seconds
        self.busy = False
        self.close_requested = False
        self.frame = 0

    async def _animate(self, app) -> None:
        while self.busy:
            await asyncio.sleep(self.interval_seconds)
            if not self.busy:
                return
            self.frame += 1
            app.invalidate()

    async def _process(
        self,
        app,
        *,
        work: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[Exception], None],
        on_idle: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        cancelled_during_shutdown = False
        try:
            loop = asyncio.get_running_loop()
            # Provider and attempt telemetry is process-local ContextVar state.
            # Copy it into the executor so making a TUI responsive does not
            # silently erase the same study records produced synchronously.
            context = copy_context()
            worker = loop.run_in_executor(None, context.run, work)
            try:
                result = await asyncio.shield(worker)
            except asyncio.CancelledError:
                # Executor work cannot be safely cancelled. Commit the frozen
                # read-only turn before prompt-toolkit finishes task cleanup.
                cancelled_during_shutdown = True
                result = await worker
            try:
                on_success(result)
            except Exception as error:
                on_error(error)
        except Exception as error:
            on_error(error)
        finally:
            self.busy = False

        if cancelled_during_shutdown:
            raise asyncio.CancelledError()
        if self.close_requested:
            on_close()
        else:
            on_idle()
        app.invalidate()

    def start(
        self,
        app,
        *,
        work: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[Exception], None],
        on_idle: Callable[[], None],
        on_close: Callable[[], None],
    ) -> bool:
        """Start one frozen turn; return false when another already owns it."""

        if self.busy:
            return False
        self.busy = True
        self.close_requested = False
        self.frame = 0
        app.create_background_task(self._animate(app))
        app.create_background_task(
            self._process(
                app,
                work=work,
                on_success=on_success,
                on_error=on_error,
                on_idle=on_idle,
                on_close=on_close,
            )
        )
        return True

    def request_close(self) -> bool:
        """Defer closing while executor work owns the reviewed frozen turn."""

        if not self.busy:
            return False
        self.close_requested = True
        return True
