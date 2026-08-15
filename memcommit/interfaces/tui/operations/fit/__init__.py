"""Fit TUI projection and standalone Viewer adapter."""

from memcommit.interfaces.tui.operations.fit.adapter import (
    project_fit_clipboard,
    project_fit_result,
)
from memcommit.interfaces.tui.operations.fit.model import FitClipboardProjection
from memcommit.interfaces.tui.operations.fit.screen import run_fit_tui

__all__ = [
    "FitClipboardProjection",
    "project_fit_clipboard",
    "project_fit_result",
    "run_fit_tui",
]
