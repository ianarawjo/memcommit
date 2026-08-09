"""Compatibility facade for the generic exact Context-name control."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.context_targeting.tui.name_editor import (
    ContextNameEditorState,
    ContextNameView,
    context_name_card_lines,
    context_name_row_fragments,
    context_name_tree_fragments,
)


@dataclass(frozen=True)
class SaveLocationView(ContextNameView):
    """Resolution-specific label adapter for the shared Context-name view."""

    label: str = "SAVE LOCATION"
    detail: str = "Enter to change this exact local Context name."


SaveLocationEditorState = ContextNameEditorState
save_location_tree_fragments = context_name_tree_fragments
save_location_row_fragments = context_name_row_fragments
save_location_card_lines = context_name_card_lines


__all__ = [
    "SaveLocationEditorState",
    "SaveLocationView",
    "save_location_card_lines",
    "save_location_row_fragments",
    "save_location_tree_fragments",
]
