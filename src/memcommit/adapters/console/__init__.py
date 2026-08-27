"""Console-host routing shared by plain CLI and interactive TUI adapters."""

from memcommit.adapters.console.router import (
    ConsoleMode,
    ConsoleModeError,
    ConsoleRunner,
    resolve_console_mode,
)
from memcommit.adapters.console.terminal import (
    SystemTerminalCapabilities,
    TerminalCapabilities,
    is_interactive_terminal,
    require_interactive_terminal,
)

__all__ = [
    "ConsoleMode",
    "ConsoleModeError",
    "ConsoleRunner",
    "SystemTerminalCapabilities",
    "TerminalCapabilities",
    "is_interactive_terminal",
    "require_interactive_terminal",
    "resolve_console_mode",
]
