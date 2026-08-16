"""Compatibility exports for the shared Context-targeting picker.

The implementation moved to :mod:`memcommit.context_targeting.tui.picker` so
operation and interface adapters can depend on a neutral owner.  Keep this
module behavior-free while older callers migrate.
"""

# ruff: noqa: F401 - compatibility imports are this module's complete purpose.

from memcommit.context_targeting.tui.picker import (
    CONTEXT_PICKER_STYLE,
    ContextMemoryBadge,
    ContextMemoryPreviewController,
    ContextMemoryRow,
    ContextMemorySelection,
    ContextPickerClipboardProjection,
    ContextPickerNavigationUnit,
    ContextSubtreeSelection,
    ContextTree,
    ContextTreeState,
    _CONTEXT_NAVIGATION_HINT,
    _CONTEXT_PICKER_STYLE,
    _build_context_tree,
    _context_ancestors,
    _expandable_context_subtree,
    _render_context_options,
    _render_context_roots,
    _visible_context_rows,
    build_context_tree,
    choose_context,
    context_memory_rows,
    context_option_continuation_prefixes,
    context_picker_navigation_units,
    project_context_picker_clipboard,
    render_context_memory_previews,
    render_context_options,
    render_context_roots,
)

__all__ = [
    "CONTEXT_PICKER_STYLE",
    "ContextMemoryBadge",
    "ContextMemoryPreviewController",
    "ContextMemoryRow",
    "ContextMemorySelection",
    "ContextPickerClipboardProjection",
    "ContextPickerNavigationUnit",
    "ContextSubtreeSelection",
    "ContextTree",
    "ContextTreeState",
    "build_context_tree",
    "choose_context",
    "context_memory_rows",
    "context_option_continuation_prefixes",
    "context_picker_navigation_units",
    "project_context_picker_clipboard",
    "render_context_memory_previews",
    "render_context_options",
    "render_context_roots",
]
