"""Fit TUI projection and standalone Viewer adapter."""

from memcommit.interfaces.tui.operations.fit.adapter import (
    project_proposition_fit_clipboard,
    project_proposition_fit_result,
    project_fit_clipboard,
    project_fit_result,
)
from memcommit.interfaces.tui.operations.fit.model import FitClipboardProjection
from memcommit.interfaces.tui.operations.fit.screen import (
    run_fit_tui,
    run_proposition_fit_tui,
)

__all__ = [
    "FitClipboardProjection",
    "project_proposition_fit_clipboard",
    "project_proposition_fit_result",
    "project_fit_clipboard",
    "project_fit_result",
    "run_proposition_fit_tui",
    "run_fit_tui",
]
