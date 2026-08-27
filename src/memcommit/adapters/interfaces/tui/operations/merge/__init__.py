"""Interactive Source/range setup for structural Merge."""

from memcommit.adapters.interfaces.tui.operations.merge.adapter import (
    build_merge_tui_setup,
)
from memcommit.adapters.interfaces.tui.operations.merge.model import MergeTuiSetup
from memcommit.adapters.interfaces.tui.operations.merge.screen import (
    merge_exact_command_review,
    merge_plan_exact_command_review,
    project_merge_plan,
    run_merge_plan_review,
)
from memcommit.adapters.interfaces.tui.operations.merge.resolution import (
    merge_resolution_exact_review,
    merge_resolution_spec,
    run_merge_conflict_review,
)
from memcommit.adapters.interfaces.tui.operations.merge.setup import (
    choose_merge_setup,
    merge_endpoint_setup_spec,
)

__all__ = [
    "MergeTuiSetup",
    "build_merge_tui_setup",
    "choose_merge_setup",
    "merge_exact_command_review",
    "merge_endpoint_setup_spec",
    "merge_plan_exact_command_review",
    "project_merge_plan",
    "run_merge_plan_review",
    "merge_resolution_exact_review",
    "merge_resolution_spec",
    "run_merge_conflict_review",
]
