"""Interactive Source/range setup for structural Merge."""

from memcommit.interfaces.tui.operations.merge.adapter import (
    build_merge_tui_setup,
)
from memcommit.interfaces.tui.operations.merge.model import MergeTuiSetup
from memcommit.interfaces.tui.operations.merge.screen import (
    merge_exact_command_review,
    run_merge_tui,
)

__all__ = [
    "MergeTuiSetup",
    "build_merge_tui_setup",
    "merge_exact_command_review",
    "run_merge_tui",
]
