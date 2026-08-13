"""Injected terminal capabilities for console route selection."""

from __future__ import annotations

from dataclasses import dataclass, field
import sys
from typing import Protocol, TextIO


class TerminalCapabilities(Protocol):
    """Report whether a console invocation can host a full-screen TUI."""

    def is_interactive(self) -> bool:
        """Return whether both input and output are interactive terminals."""


@dataclass(frozen=True)
class SystemTerminalCapabilities:
    """Read TTY state lazily from the process streams."""

    input_stream: TextIO = field(default_factory=lambda: sys.stdin)
    output_stream: TextIO = field(default_factory=lambda: sys.stdout)

    def is_interactive(self) -> bool:
        return self.input_stream.isatty() and self.output_stream.isatty()


def is_interactive_terminal() -> bool:
    """Return whether the current process streams can host a TUI."""

    return SystemTerminalCapabilities().is_interactive()


def require_interactive_terminal(
    operation: str,
    *,
    snapshot_hint: str = "",
    terminal: TerminalCapabilities | None = None,
) -> None:
    """Fail before opening a full-screen application outside a TTY."""

    if (terminal or SystemTerminalCapabilities()).is_interactive():
        return
    message = f"{operation} requires a TTY (interactive terminal)."
    if snapshot_hint:
        message += f" {snapshot_hint}"
    raise ValueError(message)
