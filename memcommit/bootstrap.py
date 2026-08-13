"""Composition root for concrete public adapters and application callables."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.interfaces.cli.summarize import render_summarize_plain
from memcommit.interfaces.console.router import ConsoleRunner
from memcommit.interfaces.console.terminal import TerminalCapabilities
from memcommit.interfaces.tui.operations.summarize import run_summarize_tui
from memcommit.summarize_application import SummarizeRequest, SummarizeResult


def build_summarize_console_runner(
    *,
    execute: Callable[[SummarizeRequest], SummarizeResult],
    terminal: TerminalCapabilities,
) -> ConsoleRunner[SummarizeRequest, SummarizeResult]:
    """Wire independent Summarize presenters to one application callable."""

    return ConsoleRunner(
        execute=execute,
        present_plain=render_summarize_plain,
        present_tui=run_summarize_tui,
        terminal=terminal,
    )
