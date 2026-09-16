"""Operation-neutral selection state shared by console interactions."""

from memcommit.adapters.console.terminal.components.selection.model import SelectionOption
from memcommit.adapters.console.terminal.components.selection.rendering import (
    ChoiceVisualState,
    choice_marker,
    choice_visual_state,
    render_choice_card_rows,
    render_vertical_choice_cards,
    render_vertical_choice_rows,
    tree_choice_marker,
    tree_choice_styles,
)
from memcommit.adapters.console.terminal.components.selection.state import FlatMultiSelectionState, FlatSelectionState

__all__ = [
    "ChoiceVisualState",
    "FlatMultiSelectionState",
    "FlatSelectionState",
    "SelectionOption",
    "choice_marker",
    "choice_visual_state",
    "render_choice_card_rows",
    "render_vertical_choice_cards",
    "render_vertical_choice_rows",
    "tree_choice_marker",
    "tree_choice_styles",
]
