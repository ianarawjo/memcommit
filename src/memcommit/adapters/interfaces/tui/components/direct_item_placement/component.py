"""Context-tree composition for the shared direct-item placement state."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from prompt_toolkit.application.current import get_app

from memcommit.core.context_targeting.tui.selector import ContextSelectorRowProjection
from memcommit.core.context_targeting.tui.tree import ContextTreeRow
from memcommit.adapters.interfaces.tui.components.direct_item_placement.model import (
    DirectItemGapState,
    DirectItemPlacementRow,
)
from memcommit.adapters.interfaces.tui.components.direct_item_placement.rendering import (
    render_direct_item_tree_fragments,
)


@dataclass
class DirectItemPlacementTreeProjection:
    """Compose one target's ordered items into the shared Context selector."""

    context_name: str
    state: DirectItemGapState
    editing: bool = False

    @classmethod
    def create(
        cls,
        context_name: str,
        rows: Sequence[DirectItemPlacementRow],
    ) -> "DirectItemPlacementTreeProjection":
        return cls(
            context_name,
            DirectItemGapState.create(rows, insertion_label="POSITION"),
        )

    def begin(self) -> None:
        self.state.cursor_position = self.state.selected_position
        self.editing = True

    def end(self) -> None:
        self.editing = False

    def project(
        self,
        row: ContextTreeRow,
        focused: bool,
    ) -> ContextSelectorRowProjection:
        if row.name != self.context_name:
            return ContextSelectorRowProjection()
        return ContextSelectorRowProjection(
            branch="▾",
            nested_fragments=tuple(
                render_direct_item_tree_fragments(
                    self.state,
                    row=row,
                    editing=self.editing,
                    focused=focused,
                    width=max(24, get_app().output.get_size().columns - 2),
                )
            ),
            show_context_cursor=not self.editing,
        )

    def replace_context(
        self,
        context_name: str,
        rows: Sequence[DirectItemPlacementRow],
    ) -> None:
        self.context_name = context_name
        self.state.replace_rows(rows)
        self.editing = False
