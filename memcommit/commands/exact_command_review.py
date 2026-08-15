"""Compatibility imports for the shared exact-command review component."""

from memcommit.exact_command_review import ExactCommandReview
from memcommit.interfaces.tui.components.exact_command_review.rendering import (
    format_exact_command,
    render_exact_command_blocks,
    render_exact_command_review,
)

__all__ = [
    "ExactCommandReview",
    "format_exact_command",
    "render_exact_command_blocks",
    "render_exact_command_review",
]
