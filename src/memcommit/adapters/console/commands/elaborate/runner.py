"""Console-mode composition for read-only Elaborate proposals."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.adapters.console.commands.elaborate.proposal import (
    render_elaborate_plain,
)
from memcommit.adapters.console.commands.elaborate.viewer import run_elaborate_tui
from memcommit.adapters.console.router import ConsoleRunner
from memcommit.adapters.console.terminal import TerminalCapabilities
from memcommit.adapters.interfaces.tui.components.plain_text_clipboard import (
    ClipboardWriter,
)
from memcommit.application.operations.elaborate.application import (
    ElaborateRequest,
    ElaborateResult,
)


def build_elaborate_console_runner(
    *,
    execute: Callable[[ElaborateRequest], ElaborateResult],
    clipboard_writer: ClipboardWriter,
    terminal: TerminalCapabilities,
) -> ConsoleRunner[ElaborateRequest, ElaborateResult]:
    """Wire Elaborate proposal presenters to one typed use case."""

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


__all__ = ["build_elaborate_console_runner"]
