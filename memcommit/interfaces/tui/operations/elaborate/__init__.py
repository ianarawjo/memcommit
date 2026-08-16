"""Elaborate TUI projection and standalone Viewer adapter."""

from memcommit.interfaces.tui.operations.elaborate.adapter import (
    project_elaborate_clipboard,
    project_elaborate_result,
)
from memcommit.interfaces.tui.operations.elaborate.model import (
    ElaborateClipboardProjection,
)
from memcommit.interfaces.tui.operations.elaborate.screen import run_elaborate_tui

__all__ = [
    "ElaborateClipboardProjection",
    "project_elaborate_clipboard",
    "project_elaborate_result",
    "run_elaborate_tui",
]
