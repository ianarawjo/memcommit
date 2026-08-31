"""Distill proposal workbench and typed projections."""

from memcommit.adapters.console.commands.semantic_updates.derive.distill.workbench.model import (
    DistillClipboardProjection,
    DistillTuiSetup,
)
from memcommit.adapters.console.commands.semantic_updates.derive.distill.workbench.presentation import (
    project_distill_clipboard,
    project_distill_result,
)
from memcommit.adapters.console.commands.semantic_updates.derive.distill.workbench.screen import run_distill_tui

__all__ = [
    "DistillClipboardProjection",
    "DistillTuiSetup",
    "project_distill_clipboard",
    "project_distill_result",
    "run_distill_tui",
]
