"""Presentation-mode routing above independent CLI and TUI adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generic, TypeVar

from memcommit.adapters.console.terminal.core.capabilities import TerminalCapabilities


RequestT = TypeVar("RequestT")
ResultT = TypeVar("ResultT")


class ConsoleMode(str, Enum):
    """The explicit or automatically selected console presentation route."""

    AUTO = "AUTO"
    PLAIN = "PLAIN"
    TUI = "TUI"


class ConsoleModeError(ValueError):
    """The requested presentation route is ambiguous or unavailable."""


def resolve_console_mode(*, plain: bool, tui: bool) -> ConsoleMode:
    """Resolve mutually exclusive presentation flags without touching a TTY."""

    if type(plain) is not bool or type(tui) is not bool:
        raise TypeError("Console presentation flags must be booleans.")
    if plain and tui:
        raise ConsoleModeError("Choose either --plain or --tui, not both.")
    if plain:
        return ConsoleMode.PLAIN
    if tui:
        return ConsoleMode.TUI
    return ConsoleMode.AUTO


@dataclass(frozen=True)
class ConsoleRunner(Generic[RequestT, ResultT]):
    """Route one use case through an injected plain or interactive adapter.

    This is the only object that knows both presentation siblings. The CLI and
    TUI adapters remain independent, while the application callable receives
    no terminal state or rendering concern.  The interactive adapter owns when
    execution begins so a setup screen can be cancelled before semantic or
    durable infrastructure is touched.
    """

    execute: Callable[[RequestT], ResultT]
    present_plain: Callable[[ResultT], None]
    run_tui: Callable[
        [RequestT, Callable[[RequestT], ResultT]],
        ResultT | None,
    ]
    terminal: TerminalCapabilities

    def run(self, request: RequestT, *, mode: ConsoleMode) -> ResultT | None:
        if not isinstance(mode, ConsoleMode):
            raise TypeError("Console mode is invalid.")
        interactive = self.terminal.is_interactive()
        if mode is ConsoleMode.TUI and not interactive:
            raise ConsoleModeError(
                "Interactive presentation requires a TTY; use --plain instead."
            )
        selected = (
            ConsoleMode.TUI
            if mode is ConsoleMode.AUTO and interactive
            else ConsoleMode.PLAIN
            if mode is ConsoleMode.AUTO
            else mode
        )
        if selected is ConsoleMode.TUI:
            return self.run_tui(request, self.execute)
        result = self.execute(request)
        self.present_plain(result)
        return result
