"""Summarize console workbench projection and screen adapter."""

from memcommit.adapters.console.commands.search_explain.synthesize.summarize.workbench.presentation import (
    project_summarize_clipboard,
    project_summarize_outcome,
    project_summarize_result,
)
from memcommit.adapters.console.commands.search_explain.synthesize.summarize.workbench.model import (
    SummarizeClipboardProjection,
    SummarizeTuiOutcome,
    SummarizeTuiSetup,
)
from memcommit.adapters.console.commands.search_explain.synthesize.summarize.workbench.screen import (
    run_summarize_tui,
)

__all__ = [
    "project_summarize_result",
    "project_summarize_outcome",
    "project_summarize_clipboard",
    "run_summarize_tui",
    "SummarizeClipboardProjection",
    "SummarizeTuiOutcome",
    "SummarizeTuiSetup",
]
