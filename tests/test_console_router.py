"""Contracts for console presentation routing above application use cases."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from memcommit.adapters.console import (
    ConsoleMode,
    ConsoleModeError,
    ConsoleRunner,
    resolve_console_mode,
)


@dataclass(frozen=True)
class _Terminal:
    interactive: bool

    def is_interactive(self) -> bool:
        return self.interactive


def test_auto_routes_one_application_result_to_tui_on_terminal() -> None:
    events: list[tuple[str, object]] = []

    def run_tui(request, execute):
        events.append(("tui", request))
        return execute(request)

    runner = ConsoleRunner(
        execute=lambda request: events.append(("execute", request)) or "result",
        present_plain=lambda result: events.append(("plain", result)),
        run_tui=run_tui,
        terminal=_Terminal(True),
    )

    assert runner.run("request", mode=ConsoleMode.AUTO) == "result"
    assert events == [("tui", "request"), ("execute", "request")]


def test_tui_can_cancel_before_application_execution() -> None:
    events: list[tuple[str, object]] = []
    runner = ConsoleRunner(
        execute=lambda request: events.append(("execute", request)) or "result",
        present_plain=lambda result: events.append(("plain", result)),
        run_tui=lambda request, _execute: events.append(("tui", request)) or None,
        terminal=_Terminal(True),
    )

    assert runner.run("request", mode=ConsoleMode.TUI) is None
    assert events == [("tui", "request")]


def test_auto_routes_the_same_application_result_to_plain_without_tty() -> None:
    events: list[tuple[str, object]] = []
    runner = ConsoleRunner(
        execute=lambda request: events.append(("execute", request)) or "result",
        present_plain=lambda result: events.append(("plain", result)),
        run_tui=lambda request, _execute: events.append(("tui", request)),
        terminal=_Terminal(False),
    )

    runner.run("request", mode=ConsoleMode.AUTO)

    assert events == [("execute", "request"), ("plain", "result")]


def test_forced_tui_fails_before_application_execution_without_tty() -> None:
    executed: list[object] = []
    runner = ConsoleRunner(
        execute=lambda request: executed.append(request),
        present_plain=lambda _result: None,
        run_tui=lambda _request, _execute: None,
        terminal=_Terminal(False),
    )

    with pytest.raises(ConsoleModeError, match="requires a TTY"):
        runner.run("request", mode=ConsoleMode.TUI)

    assert executed == []


def test_explicit_plain_never_opens_tui_on_terminal() -> None:
    presentations: list[str] = []
    ConsoleRunner(
        execute=lambda request: request,
        present_plain=lambda _result: presentations.append("plain"),
        run_tui=lambda _request, _execute: presentations.append("tui"),
        terminal=_Terminal(True),
    ).run("result", mode=ConsoleMode.PLAIN)

    assert presentations == ["plain"]


def test_console_flags_are_mutually_exclusive() -> None:
    assert resolve_console_mode(plain=False, tui=False) is ConsoleMode.AUTO
    assert resolve_console_mode(plain=True, tui=False) is ConsoleMode.PLAIN
    assert resolve_console_mode(plain=False, tui=True) is ConsoleMode.TUI
    with pytest.raises(ConsoleModeError, match="either --plain or --tui"):
        resolve_console_mode(plain=True, tui=True)
