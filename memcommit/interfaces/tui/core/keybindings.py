"""Operation-neutral key binding and layered-back mechanics."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Callable

from prompt_toolkit.filters import FilterOrBool
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys


def bind_case_insensitive_key(
    bindings: KeyBindings,
    key: str,
    *,
    filter: FilterOrBool = True,
    eager: FilterOrBool = False,
) -> Callable[
    [Callable[[KeyPressEvent], None]],
    Callable[[KeyPressEvent], None],
]:
    """Bind one alphabetic shortcut in both lowercase and uppercase forms."""

    if len(key) != 1 or not key.isalpha():
        raise ValueError("Case-insensitive shortcuts require one alphabetic key.")
    lower, upper = key.lower(), key.upper()

    def decorator(
        handler: Callable[[KeyPressEvent], None],
    ) -> Callable[[KeyPressEvent], None]:
        bindings.add(lower, filter=filter, eager=eager)(handler)
        bindings.add(upper, filter=filter, eager=eager)(handler)
        return handler

    return decorator


def bind_tui_interrupt(
    bindings: KeyBindings,
    close: Callable[[KeyPressEvent], None],
) -> None:
    """Bind terminal interrupt input to an operation-owned safe close."""

    bindings.add("c-c", eager=True)(close)
    bindings.add(Keys.SIGINT, eager=True)(close)


@dataclass
class NavigationAccelerator:
    """Increase held-arrow rate while keeping deliberate taps precise."""

    direction: int = 0
    streak: int = 0
    last_at: float | None = None
    repeat_candidate: bool = False
    repeat_interval: float = 0.08
    _animation_generation: int = 0
    _animation_task: asyncio.Task[None] | None = None

    _INITIAL_REPEAT_DELAY_MIN = 0.2
    _INITIAL_REPEAT_DELAY_MAX = 1.2
    _REPEAT_INTERVAL_MAX = 0.16
    _MIN_FRAME_INTERVAL = 1 / 60

    def reset(self) -> None:
        self._animation_generation += 1
        if self._animation_task is not None:
            self._animation_task.cancel()
            self._animation_task = None
        self.direction = 0
        self.streak = 0
        self.last_at = None
        self.repeat_candidate = False

    def step(self, direction: int, *, now: float | None = None) -> int:
        if direction not in {-1, 1}:
            raise ValueError("Navigation direction must be -1 or 1.")
        observed_at = monotonic() if now is None else now
        if self.last_at is None or direction != self.direction:
            self.direction = direction
            self.streak = 0
            self.last_at = observed_at
            self.repeat_candidate = False
            return 1

        interval = observed_at - self.last_at
        self.last_at = observed_at
        if interval < 0:
            self.streak = 0
            self.repeat_candidate = False
        elif self.repeat_candidate and interval <= self._REPEAT_INTERVAL_MAX:
            self.streak += 1
            self.repeat_interval = interval
        else:
            self.repeat_candidate = (
                self._INITIAL_REPEAT_DELAY_MIN
                <= interval
                <= self._INITIAL_REPEAT_DELAY_MAX
            )
            self.streak = 0

        if self.streak >= 9:
            return 5
        if self.streak >= 4:
            return 2
        return 1

    def move(
        self,
        direction: int,
        *,
        app,
        move_one: Callable[[int], None],
        now: float | None = None,
    ) -> None:
        """Move now, then animate every additional held-key row in order."""

        multiplier = self.step(direction, now=now)
        self._animation_generation += 1
        generation = self._animation_generation
        if self._animation_task is not None:
            self._animation_task.cancel()
            self._animation_task = None

        move_one(direction)
        app.invalidate()
        if multiplier == 1:
            return

        interval = max(self._MIN_FRAME_INTERVAL, self.repeat_interval / multiplier)

        async def animate_remaining() -> None:
            try:
                for _ in range(multiplier - 1):
                    await asyncio.sleep(interval)
                    if generation != self._animation_generation:
                        return
                    move_one(direction)
                    app.invalidate()
            finally:
                if generation == self._animation_generation:
                    self._animation_task = None

        self._animation_task = app.create_background_task(animate_remaining())


def dispatch_tui_back(
    event: object,
    *steps: Callable[[object], bool],
    close: Callable[[object], None],
) -> None:
    """Unwind one visible UI layer, or delegate closing to the operation."""

    for step in steps:
        if step(event):
            getattr(event, "app").invalidate()
            return
    close(event)
