"""Convenience exports for the smallest reusable terminal primitives."""

from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldControl,
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.adapters.console.terminal.components.report_card import boxed_lines
from memcommit.adapters.console.terminal.components.tree_row import navigable_tree_row_prefix
from memcommit.adapters.console.terminal.components.viewport_anchor import anchored_fragments

__all__ = [
    "ExactNameFieldControl",
    "ExactNameFieldView",
    "ExactNameInputControl",
    "anchored_fragments",
    "boxed_lines",
    "navigable_tree_row_prefix",
]
