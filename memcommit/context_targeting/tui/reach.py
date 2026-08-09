"""Shared exact-versus-descendant control for terminal shells."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)


@dataclass
class ContextReachState:
    """Standard exact-versus-descendant scope independent of operation meaning."""

    choice: HorizontalChoiceState

    @classmethod
    def create(cls, *, include_descendants: bool) -> "ContextReachState":
        return cls(
            HorizontalChoiceState(
                (
                    HorizontalChoiceOption("EXACT", "THIS CONTEXT ONLY"),
                    HorizontalChoiceOption("SUBTREE", "INCLUDE DESCENDANTS"),
                ),
                selected_uid="SUBTREE" if include_descendants else "EXACT",
            )
        )

    @property
    def include_descendants(self) -> bool:
        return self.choice.selected_uid == "SUBTREE"

    def move(self, delta: int) -> bool:
        return self.choice.move(delta)


def render_context_reach(
    state: ContextReachState,
    *,
    focused: bool,
    title: str = "RANGE",
) -> StyleAndTextTuples:
    """Render the same reach vocabulary and segmented control everywhere."""

    return render_horizontal_choice(state.choice, title=title, focused=focused)
