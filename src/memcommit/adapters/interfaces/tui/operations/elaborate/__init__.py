"""Elaborate TUI projection and standalone Viewer adapter."""

from memcommit.adapters.interfaces.tui.operations.elaborate.adapter import (
    project_elaborate_clipboard,
    project_elaborate_result,
)
from memcommit.adapters.interfaces.tui.operations.elaborate.model import (
    ElaborateClipboardProjection,
)
from memcommit.adapters.interfaces.tui.operations.elaborate.screen import run_elaborate_tui

__all__ = [
    "ElaborateClipboardProjection",
    "project_elaborate_clipboard",
    "project_elaborate_result",
    "run_elaborate_tui",
]
