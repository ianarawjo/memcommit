"""Deterministic Replace terminal adapter."""

from memcommit.adapters.interfaces.tui.operations.replace.model import ReplaceTuiSetup
from memcommit.adapters.interfaces.tui.operations.replace.screen import run_replace_tui

__all__ = ["ReplaceTuiSetup", "run_replace_tui"]
