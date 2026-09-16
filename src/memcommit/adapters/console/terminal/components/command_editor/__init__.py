"""Shared command projection, editing, rendering, and approval components."""

from memcommit.adapters.console.terminal.components.command_editor.approval import (
    approve_exact_command,
)
from memcommit.adapters.console.terminal.components.command_editor.control import (
    CommandEditorControl,
)
from memcommit.adapters.console.terminal.components.command_editor.form import (
    CommandDraft,
    CommandForm,
    CommandFormField,
    resolve_displayed_command_value,
    shortest_unique_identifier_prefix,
)
from memcommit.adapters.console.terminal.components.command_editor.interaction import (
    bind_exact_command_approval,
)
from memcommit.adapters.console.terminal.components.command_editor.model import (
    CommandReview,
)
from memcommit.adapters.console.terminal.components.command_editor.rendering import (
    format_exact_command,
    render_exact_command_blocks,
    render_exact_command_review,
)

__all__ = [
    "CommandDraft",
    "CommandEditorControl",
    "CommandForm",
    "CommandFormField",
    "CommandReview",
    "approve_exact_command",
    "bind_exact_command_approval",
    "format_exact_command",
    "render_exact_command_blocks",
    "render_exact_command_review",
    "resolve_displayed_command_value",
    "shortest_unique_identifier_prefix",
]
