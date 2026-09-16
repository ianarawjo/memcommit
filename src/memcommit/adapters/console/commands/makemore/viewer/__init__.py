"""Makemore TUI projection and standalone Viewer adapter."""

from memcommit.adapters.console.commands.makemore.viewer.projection import (
    project_makemore_clipboard,
    project_makemore_result,
)
from memcommit.adapters.console.commands.makemore.viewer.model import (
    MakemoreClipboardProjection,
)
from memcommit.adapters.console.commands.makemore.viewer.screen import run_makemore_tui

__all__ = [
    "MakemoreClipboardProjection",
    "project_makemore_clipboard",
    "project_makemore_result",
    "run_makemore_tui",
]
