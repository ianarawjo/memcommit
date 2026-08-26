"""Distill TUI projection and shared-workbench adapter."""

from memcommit.interfaces.tui.operations.distill.adapter import (
    project_distill_clipboard,
    project_distill_result,
)
from memcommit.interfaces.tui.operations.distill.model import (
    DistillClipboardProjection,
    DistillTuiSetup,
)
from memcommit.interfaces.tui.operations.distill.screen import run_distill_tui

__all__ = [
    "DistillClipboardProjection",
    "DistillTuiSetup",
    "project_distill_clipboard",
    "project_distill_result",
    "run_distill_tui",
]
