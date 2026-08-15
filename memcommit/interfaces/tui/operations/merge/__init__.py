"""Interactive Source/range setup for structural Merge."""

from memcommit.interfaces.tui.operations.merge.adapter import (
    build_merge_tui_setup,
)
from memcommit.interfaces.tui.operations.merge.model import MergeTuiSetup
from memcommit.interfaces.tui.operations.merge.screen import (
    merge_exact_command_review,
    run_merge_tui,
)
from memcommit.interfaces.tui.operations.merge.setup import (
    choose_merge_setup,
    merge_endpoint_setup_spec,
)

__all__ = [
    "MergeTuiSetup",
    "build_merge_tui_setup",
    "choose_merge_setup",
    "merge_exact_command_review",
    "merge_endpoint_setup_spec",
    "run_merge_tui",
]
