"""Elaborate TUI projection and standalone Viewer adapter."""

from memcommit.adapters.console.commands.elaborate.viewer.projection import (
    project_elaborate_clipboard,
    project_elaborate_result,
)
from memcommit.adapters.console.commands.elaborate.viewer.model import (
    ElaborateClipboardProjection,
)
from memcommit.adapters.console.commands.elaborate.viewer.screen import run_elaborate_tui

__all__ = [
    "ElaborateClipboardProjection",
    "project_elaborate_clipboard",
    "project_elaborate_result",
    "run_elaborate_tui",
]
