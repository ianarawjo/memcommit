"""Summarize TUI projection and screen adapter."""

from memcommit.interfaces.tui.operations.summarize.adapter import (
    project_summarize_clipboard,
    project_summarize_outcome,
    project_summarize_result,
)
from memcommit.interfaces.tui.operations.summarize.model import (
    SummarizeClipboardProjection,
    SummarizeTuiOutcome,
    SummarizeTuiSetup,
)
from memcommit.interfaces.tui.operations.summarize.screen import run_summarize_tui

__all__ = [
    "project_summarize_result",
    "project_summarize_outcome",
    "project_summarize_clipboard",
    "run_summarize_tui",
    "SummarizeClipboardProjection",
    "SummarizeTuiOutcome",
    "SummarizeTuiSetup",
]
