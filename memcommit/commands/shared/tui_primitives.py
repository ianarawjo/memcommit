"""Compatibility imports for interface-owned terminal primitives."""

from memcommit.interfaces.tui.components.exact_name import (
    ExactNameFieldControl,
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.interfaces.tui.components.report_card import boxed_lines
from memcommit.interfaces.tui.components.tree_row import navigable_tree_row_prefix
from memcommit.interfaces.tui.components.viewport_anchor import anchored_fragments

__all__ = [
    "ExactNameFieldControl",
    "ExactNameFieldView",
    "ExactNameInputControl",
    "anchored_fragments",
    "boxed_lines",
    "navigable_tree_row_prefix",
]
