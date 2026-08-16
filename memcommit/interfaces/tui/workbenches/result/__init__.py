"""Shared read-only result workbench presentation."""

from memcommit.interfaces.tui.workbenches.result.shell import (
    render_result_workbench_snapshot,
    result_workbench_fragments,
    run_result_workbench_shell,
)

__all__ = [
    "render_result_workbench_snapshot",
    "result_workbench_fragments",
    "run_result_workbench_shell",
]
