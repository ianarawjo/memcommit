"""Public compatibility surface for the Resolution Session shell."""

from memcommit.adapters.interfaces.tui.workbenches.resolution.session_shell.presentation import (
    RESOLUTION_WORKBENCH_STYLE,
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    _impact_arrow_expansion,
    _seeded_report_lines,
    _seeded_report_sections,
    _session_items_fragments,
    _viewer_focus_fragments,
    render_resolution_workbench_snapshot,
    resolution_report_fragments,
    resolution_review_fragments,
    resolution_seeded_report_fragments,
    resolution_viewer_fragments,
    resolution_workbench_fragments,
    session_review_action_view,
    session_todo_view,
)
from memcommit.adapters.interfaces.tui.workbenches.resolution.session_shell.runtime import (
    run_resolution_workbench_shell,
)

__all__ = [
    "RESOLUTION_WORKBENCH_STYLE",
    "ResolutionDestination",
    "ResolutionGlobalStrategy",
    "SessionTodoView",
    "_impact_arrow_expansion",
    "_seeded_report_lines",
    "_seeded_report_sections",
    "_session_items_fragments",
    "_viewer_focus_fragments",
    "render_resolution_workbench_snapshot",
    "resolution_report_fragments",
    "resolution_review_fragments",
    "resolution_seeded_report_fragments",
    "resolution_viewer_fragments",
    "resolution_workbench_fragments",
    "run_resolution_workbench_shell",
    "session_review_action_view",
    "session_todo_view",
]
