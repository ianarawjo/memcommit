"""Composition root for concrete public adapters and application callables."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from memcommit.application.operations.elaborate.application import ElaborateRequest, ElaborateResult
from memcommit.application.operations.distill.application import DistillRequest, DistillResult
from memcommit.adapters.interfaces.cli.distill import render_distill_plain
from memcommit.adapters.interfaces.cli.elaborate import render_elaborate_plain
from memcommit.adapters.interfaces.cli.summarize import render_summarize_plain
from memcommit.adapters.interfaces.console.router import ConsoleRunner
from memcommit.adapters.interfaces.console.terminal import TerminalCapabilities
from memcommit.adapters.interfaces.tui.components.plain_text_clipboard import ClipboardWriter
from memcommit.adapters.interfaces.tui.operations.distill import (
    DistillTuiSetup,
    run_distill_tui,
)
from memcommit.adapters.interfaces.tui.operations.elaborate import run_elaborate_tui
from memcommit.adapters.interfaces.tui.operations.summarize import (
    SummarizeTuiOutcome,
    SummarizeTuiSetup,
    run_summarize_tui,
)
from memcommit.application.operations.summarize.application import SummarizeRequest, SummarizeResult


SummarizeConsoleResult: TypeAlias = SummarizeResult | SummarizeTuiOutcome


def build_elaborate_console_runner(
    *,
    execute: Callable[[ElaborateRequest], ElaborateResult],
    clipboard_writer: ClipboardWriter,
    terminal: TerminalCapabilities,
) -> ConsoleRunner[ElaborateRequest, ElaborateResult]:
    """Wire standalone Elaborate presenters to one typed use case."""

    def run_tui(
        request: ElaborateRequest,
        application_execute: Callable[[ElaborateRequest], ElaborateResult],
    ) -> ElaborateResult:
        return run_elaborate_tui(
            application_execute(request),
            clipboard_writer=clipboard_writer,
        )

    return ConsoleRunner(
        execute=execute,
        present_plain=render_elaborate_plain,
        run_tui=run_tui,
        terminal=terminal,
    )


def build_distill_console_runner(
    *,
    execute: Callable[[DistillRequest], DistillResult],
    prepare_tui: Callable[[DistillRequest], DistillTuiSetup],
    clipboard_writer: ClipboardWriter,
    terminal: TerminalCapabilities,
) -> ConsoleRunner[DistillRequest, DistillResult]:
    """Wire Distill's plain and TUI projections to one typed application."""

    def run_tui(
        request: DistillRequest,
        application_execute: Callable[[DistillRequest], DistillResult],
    ) -> DistillResult | None:
        return run_distill_tui(
            request,
            setup=prepare_tui(request),
            execute=application_execute,
            clipboard_writer=clipboard_writer,
        )

    return ConsoleRunner(
        execute=execute,
        present_plain=render_distill_plain,
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
