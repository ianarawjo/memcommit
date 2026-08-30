"""Shared terminal Context picker public API."""

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.tree import (
    ContextTreeState,
    build_context_tree,
    context_ancestors as _context_ancestors,
    expandable_context_subtree as _expandable_context_subtree,
    visible_context_rows as _visible_context_rows,
)
from memcommit.adapters.console.terminal.components.context_picker.dialog import (
    choose_context,
)
from memcommit.adapters.console.terminal.components.context_picker.model import (
    ContextMemoryBadge,
    ContextMemoryDetail,
    ContextMemoryRow,
    ContextMemorySelection,
    ContextPickerActionReceipt,
    ContextPickerClipboardProjection,
    ContextPickerNavigationUnit,
    ContextSubtreeSelection,
)
from memcommit.adapters.console.terminal.components.context_picker.preview import (
    ContextMemoryPreviewController,
    context_picker_navigation_units,
)
from memcommit.adapters.console.terminal.components.context_picker.projection import (
    context_memory_rows,
    project_context_picker_clipboard,
)
from memcommit.adapters.console.terminal.components.context_picker.rendering import (
    CONTEXT_PICKER_STYLE,
    _CONTEXT_NAVIGATION_HINT,
    _CONTEXT_PICKER_STYLE,
    context_option_continuation_prefixes,
    memory_visibility_key_hint,
    render_context_memory_detail,
    render_context_memory_previews,
    render_context_options,
    render_context_roots,
)


# Compatibility aliases preserve established focused tests and prototypes while
# production consumers import the public component values above.
_build_context_tree = build_context_tree
_render_context_options = render_context_options
_render_context_roots = render_context_roots


__all__ = [
    "CONTEXT_PICKER_STYLE",
    "_CONTEXT_NAVIGATION_HINT",
    "_CONTEXT_PICKER_STYLE",
    "_build_context_tree",
    "_context_ancestors",
    "_expandable_context_subtree",
    "_render_context_options",
    "_render_context_roots",
    "_visible_context_rows",
    "ContextMemoryBadge",
    "ContextMemoryDetail",
    "ContextMemoryPreviewController",
    "ContextMemoryRow",
    "ContextMemorySelection",
    "ContextPickerActionReceipt",
    "ContextPickerClipboardProjection",
    "ContextPickerNavigationUnit",
    "ContextSubtreeSelection",
    "ContextTreeState",
    "build_context_tree",
    "choose_context",
    "context_memory_rows",
    "context_option_continuation_prefixes",
    "context_picker_navigation_units",
    "memory_visibility_key_hint",
    "project_context_picker_clipboard",
    "render_context_memory_detail",
    "render_context_memory_previews",
    "render_context_options",
    "render_context_roots",
]
