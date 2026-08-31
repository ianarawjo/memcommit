"""Makemore TUI projection and standalone Viewer adapter."""

from memcommit.adapters.console.commands.semantic_updates.derive.makemore.viewer.projection import (
    project_makemore_clipboard,
    project_makemore_result,
)
from memcommit.adapters.console.commands.semantic_updates.derive.makemore.viewer.model import (
    MakemoreClipboardProjection,
)
from memcommit.adapters.console.commands.semantic_updates.derive.makemore.viewer.screen import run_makemore_tui

__all__ = [
    "MakemoreClipboardProjection",
    "project_makemore_clipboard",
    "project_makemore_result",
    "run_makemore_tui",
]
