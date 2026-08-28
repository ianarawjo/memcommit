"""Compatibility facade for interface-owned session Help."""

from memcommit.adapters.console.tui.components.session_help import (
    HelpActionObserver,
    HelpClosedHandler,
    HelpUnavailableHandler,
    SessionHelpController,
    bind_session_help,
    current_help_entries,
)

__all__ = [
    "HelpActionObserver",
    "HelpClosedHandler",
    "HelpUnavailableHandler",
    "SessionHelpController",
    "bind_session_help",
    "current_help_entries",
]
