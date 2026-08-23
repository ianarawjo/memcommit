"""Compatibility facade for the relocated Meld terminal adapter."""

from memcommit.interfaces.tui.operations.meld.screen import (
    MeldShellAction,
    _comparison_issue_resolution_badges,
    _line,
    run_meld_shell,
)

__all__ = [
    "MeldShellAction",
    "_comparison_issue_resolution_badges",
    "_line",
    "run_meld_shell",
]
