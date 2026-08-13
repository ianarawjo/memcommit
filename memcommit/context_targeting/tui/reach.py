"""Shared exact-versus-descendant control for terminal shells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)


ContextReachViewMode = Literal["BOTH", "EXACT", "SUBTREE"]


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


@dataclass
class ContextReachViewState:
    """Choose one or both independently rendered reach views."""

    choice: HorizontalChoiceState

    @classmethod
    def create(cls, *, mode: ContextReachViewMode) -> "ContextReachViewState":
        if mode not in {"BOTH", "EXACT", "SUBTREE"}:
            raise ValueError("Context reach view mode is invalid.")
        return cls(
            HorizontalChoiceState(
                (
                    HorizontalChoiceOption("BOTH", "BOTH"),
                    HorizontalChoiceOption("EXACT", "THIS CONTEXT ONLY"),
                    HorizontalChoiceOption("SUBTREE", "INCLUDE DESCENDANTS"),
                ),
                selected_uid=mode,
            )
        )

    @property
    def mode(self) -> ContextReachViewMode:
        selected = self.choice.selected_uid
        if selected not in {"BOTH", "EXACT", "SUBTREE"}:
            raise ValueError("Context reach view state is invalid.")
        return selected

    def move(self, delta: int) -> bool:
        return self.choice.move(delta)


def render_context_reach(
    state: ContextReachState | ContextReachViewState,
    *,
    focused: bool,
    title: str = "RANGE",
) -> StyleAndTextTuples:
    """Render the same reach vocabulary and segmented control everywhere."""

    return render_horizontal_choice(state.choice, title=title, focused=focused)
