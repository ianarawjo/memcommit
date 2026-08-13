"""Summarize TUI projection and screen adapter."""

from memcommit.interfaces.tui.operations.summarize.adapter import (
    project_summarize_result,
)
from memcommit.interfaces.tui.operations.summarize.screen import run_summarize_tui

__all__ = [
    "project_summarize_result",
    "run_summarize_tui",
]
