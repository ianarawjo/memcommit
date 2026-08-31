"""Non-blocking bridge for one synchronous Ground interpreter call."""

from __future__ import annotations

import asyncio
import threading
from functools import partial

from memcommit.adapters.console.commands.ground_workbench.ground.shell.proposal import (
    GroundInterpreter,
)


async def interpret_from_background_thread(
    interpret: GroundInterpreter,
    text: str,
) -> object:
    """Await blocking inference without making TUI shutdown join its worker."""

    loop = asyncio.get_running_loop()
    completed: asyncio.Future[object] = loop.create_future()

    def deliver(*, result: object = None, error: Exception | None = None) -> None:
        if completed.done():
            return
        if error is not None:
            completed.set_exception(error)
        else:
            completed.set_result(result)

    def worker() -> None:
        try:
            result = interpret(text)
        except Exception as error:
            callback = partial(deliver, error=error)
        else:
            callback = partial(deliver, result=result)
        try:
            loop.call_soon_threadsafe(callback)
        except RuntimeError:
            # Escape may close the event loop before a non-cancellable
            # provider process returns. Its late result has no UI authority.
            return

    threading.Thread(
        target=worker,
        name="mem-ground-dialogue",
        daemon=True,
    ).start()
    return await completed
