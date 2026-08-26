"""Terminal-neutral classification and routing for one console invocation.

This module deliberately lives at the package root during the incremental
distribution migration. The current wheel enumerates packages manually, so a
new nested ``interfaces.console`` package would be omitted from installed
artifacts until the packaging boundary is fixed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import click
from click.core import ParameterSource


class InvocationShape(str, Enum):
    """Whether the person invoked an operation bare or supplied any input."""

    BARE = "BARE"
    EXPLICIT = "EXPLICIT"


class ConsoleRoute(str, Enum):
    """Presentation adapter selected for one parsed operation invocation."""

    PLAIN = "PLAIN"
    TUI = "TUI"


@dataclass(frozen=True)
class TerminalCapabilities:
    """The process-local terminal facts relevant to interactive eligibility."""

    stdin_is_tty: bool
    stdout_is_tty: bool

    def __post_init__(self) -> None:
        if type(self.stdin_is_tty) is not bool or type(self.stdout_is_tty) is not bool:
            raise TypeError("Terminal capability values must be booleans.")

    @property
    def interactive(self) -> bool:
        return self.stdin_is_tty and self.stdout_is_tty


def classify_click_invocation(
    context: click.Context | None = None,
) -> InvocationShape:
    """Classify explicitly supplied operands/options from Click provenance.

    Comparing parsed values with defaults is insufficient: ``--limit 5`` is
    explicit even when five is also the default, and a negative boolean option
    can explicitly select ``False``. Click retains the required provenance for
    both positional operands and options.
    """

    active = context or click.get_current_context(silent=True)
    if active is None:
        raise RuntimeError("No active console command is available to classify.")
    for name in active.params:
        if active.get_parameter_source(name) is ParameterSource.COMMANDLINE:
            return InvocationShape.EXPLICIT
    return InvocationShape.BARE


def select_console_route(
    invocation: InvocationShape,
    *,
    terminal: TerminalCapabilities,
    supports_tui: bool,
) -> ConsoleRoute:
    """Select TUI only for a truly bare, TUI-capable interactive invocation."""

    if not isinstance(invocation, InvocationShape):
        raise TypeError("Console invocation shape is invalid.")
    if not isinstance(terminal, TerminalCapabilities):
        raise TypeError("Terminal capabilities are invalid.")
    if type(supports_tui) is not bool:
        raise TypeError("TUI support must be a boolean.")
    if (
        invocation is InvocationShape.BARE
        and supports_tui
        and terminal.interactive
    ):
        return ConsoleRoute.TUI
    return ConsoleRoute.PLAIN
