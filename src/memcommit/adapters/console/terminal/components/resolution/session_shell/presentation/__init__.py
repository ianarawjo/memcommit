"""Compatibility facade for Resolution Session presentation responsibilities."""

from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.formatting import (
    RESOLUTION_WORKBENCH_STYLE,
    _indented as _indented,
    _item_kind_label as _item_kind_label,
    _line as _line,
    _source_memory_lines as _source_memory_lines,
    _visual_pad as _visual_pad,
    _visual_width as _visual_width,
    _visual_wrap as _visual_wrap,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.inspection import (
    _evidence_section_count as _evidence_section_count,
    _memory_row_section_uid as _memory_row_section_uid,
    _session_items_fragments as _session_items_fragments,
    _stable_sections as _stable_sections,
    _stacked_horizontal_key_message as _stacked_horizontal_key_message,
    _viewer_focus_fragments as _viewer_focus_fragments,
    render_resolution_workbench_snapshot,
    resolution_viewer_fragments,
    resolution_workbench_fragments,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.progression import (
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    _item_draft as _item_draft,
    _item_is_answered as _item_is_answered,
    _report_action as _report_action,
    _review_count_text as _review_count_text,
    resolution_review_fragments,
    session_review_action_view,
    session_todo_view,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation.reporting import (
    _current_impact as _current_impact,
    _impact_arrow_expansion as _impact_arrow_expansion,
    _impact_entry_item as _impact_entry_item,
    _impact_entry_section_uid as _impact_entry_section_uid,
    _impact_lines as _impact_lines,
    _impact_repeats_results as _impact_repeats_results,
    _impact_treatment_style as _impact_treatment_style,
    _seeded_report_lines as _seeded_report_lines,
    _seeded_report_sections as _seeded_report_sections,
    _visual_wrap_diff_spans as _visual_wrap_diff_spans,
    resolution_report_fragments,
    resolution_seeded_report_fragments,
)

__all__ = [
    "RESOLUTION_WORKBENCH_STYLE",
    "ResolutionDestination",
    "ResolutionGlobalStrategy",
    "SessionTodoView",
    "render_resolution_workbench_snapshot",
    "resolution_report_fragments",
    "resolution_review_fragments",
    "resolution_seeded_report_fragments",
    "resolution_viewer_fragments",
    "resolution_workbench_fragments",
    "session_review_action_view",
    "session_todo_view",
]
