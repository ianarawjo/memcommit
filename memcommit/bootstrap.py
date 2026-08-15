"""Composition root for concrete public adapters and application callables."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from memcommit.fit_application import FitRequest, FitResult
from memcommit.interfaces.cli.fit import render_fit_plain
from memcommit.interfaces.cli.summarize import render_summarize_plain
from memcommit.interfaces.console.router import ConsoleRunner
from memcommit.interfaces.console.terminal import TerminalCapabilities
from memcommit.interfaces.tui.components.plain_text_clipboard import ClipboardWriter
from memcommit.interfaces.tui.operations.fit import run_fit_tui
from memcommit.interfaces.tui.operations.summarize import (
    SummarizeTuiOutcome,
    SummarizeTuiSetup,
    run_summarize_tui,
)
from memcommit.summarize_application import SummarizeRequest, SummarizeResult


SummarizeConsoleResult: TypeAlias = SummarizeResult | SummarizeTuiOutcome


def build_fit_console_runner(
    *,
    execute: Callable[[FitRequest], FitResult],
    clipboard_writer: ClipboardWriter,
    terminal: TerminalCapabilities,
) -> ConsoleRunner[FitRequest, FitResult]:
    """Wire Fit's plain and TUI siblings to one typed runtime callable."""

    def run_tui(
        request: FitRequest,
        application_execute: Callable[[FitRequest], FitResult],
    ) -> FitResult:
        result = application_execute(request)
        return run_fit_tui(result, clipboard_writer=clipboard_writer)

    return ConsoleRunner(
        execute=execute,
        present_plain=render_fit_plain,
        run_tui=run_tui,
        terminal=terminal,
    )


def build_summarize_console_runner(
    *,
    execute: Callable[[SummarizeRequest], SummarizeResult],
    prepare_tui: Callable[[SummarizeRequest], SummarizeTuiSetup],
    clipboard_writer: Callable[[str], None],
    terminal: TerminalCapabilities,
) -> ConsoleRunner[SummarizeRequest, SummarizeConsoleResult]:
    """Wire independent Summarize presenters to one application callable."""

    def execute_console(request: SummarizeRequest) -> SummarizeConsoleResult:
        return execute(request)

    def present_plain(result: SummarizeConsoleResult) -> None:
        if not isinstance(result, SummarizeResult):
            raise TypeError("Plain Summarize requires one application result.")
        render_summarize_plain(result)

    def run_tui(
        request: SummarizeRequest,
        application_execute: Callable[
            [SummarizeRequest],
            SummarizeConsoleResult,
        ],
    ) -> SummarizeConsoleResult | None:
        def execute_one(next_request: SummarizeRequest) -> SummarizeResult:
            result = application_execute(next_request)
            if not isinstance(result, SummarizeResult):
                raise TypeError("Summarize application returned an invalid result.")
            return result

        return run_summarize_tui(
            request,
            setup=prepare_tui(request),
            execute=execute_one,
            clipboard_writer=clipboard_writer,
        )

    return ConsoleRunner(
        execute=execute_console,
        present_plain=present_plain,
        run_tui=run_tui,
        terminal=terminal,
    )
