"""Small process-local left/right choice presentation for terminal shells."""

from __future__ import annotations

from dataclasses import dataclass, field

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.interfaces.console.text import display_escape_text
from memcommit.selection.model import SelectionOption
from memcommit.selection.state import FlatSelectionState
from memcommit.selection.tui import (
    choice_marker,
    choice_visual_state,
    render_choice_card_rows,
)


@dataclass(frozen=True)
class HorizontalChoiceOption(SelectionOption):
    """One common option constrained to the horizontal control's one-line UI."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if any(character in self.description for character in "\r\n"):
            raise ValueError("Horizontal choice descriptions must stay on one line.")


@dataclass
class HorizontalChoiceState:
    """Immediate, reversible selection over a fixed ordered option set."""

    options: tuple[HorizontalChoiceOption, ...]
    selected_uid: str
    _selection: FlatSelectionState = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._selection = FlatSelectionState(
            self.options,
            cursor_uid=self.selected_uid,
            selected_uid=self.selected_uid,
            allow_empty=False,
        )

    @property
    def selected_index(self) -> int:
        return self._selection.cursor_index

    def move(self, delta: int) -> bool:
        """Move without wrapping and report whether the value changed."""
        changed = self._selection.move(delta)
        self._selection.select_cursor(toggle=False)
        self.selected_uid = self._selection.selected_uid or self.selected_uid
        return changed

    def choose(self, uid: str) -> bool:
        """Select one exact option without exposing the shared flat state."""

        if all(option.uid != uid for option in self.options):
            raise ValueError("Horizontal choice value is unavailable.")
        changed = self._selection.set_selected(uid)
        self._selection.cursor_uid = uid
        self.selected_uid = uid
        return changed


def render_horizontal_choice(
    state: HorizontalChoiceState,
    *,
    title: str,
    focused: bool,
    show_description: bool = False,
    boxed: bool = False,
    inline_boxed: bool = False,
) -> StyleAndTextTuples:
    """Render one segmented row; callers retain all meaning and key bindings."""
    if boxed and inline_boxed:
        raise ValueError("A horizontal choice cannot use two box layouts.")
    if inline_boxed:
        return _render_inline_boxed_horizontal_choice(
            state,
            title=title,
            focused=focused,
            show_description=show_description,
        )
    if boxed:
        return _render_boxed_horizontal_choice(
            state,
            title=title,
            focused=focused,
            show_description=show_description,
        )
    fragments: StyleAndTextTuples = [("", f"{'›' if focused else ' '} {title} · ")]
    for index, option in enumerate(state.options):
        selected = option.uid == state.selected_uid
        visual = choice_visual_state(
            cursor=selected,
            selected=selected,
            focused=focused,
        )
        fragments.append(
            (
                visual.content_style,
                f"[ {display_escape_text(option.label)} ]",
            )
        )
        if index < len(state.options) - 1:
            fragments.append(("", "  "))
    fragments.append(("", " · ←/→ SELECT"))
    selected = state.options[state.selected_index]
    if show_description and selected.description:
        fragments.extend(
            [
                ("", "\n"),
                ("", f"  MEANING · {display_escape_text(selected.description)}"),
            ]
        )
    return fragments


def _render_inline_boxed_horizontal_choice(
    state: HorizontalChoiceState,
    *,
    title: str,
    focused: bool,
    show_description: bool,
) -> StyleAndTextTuples:
    """Render checked choices as compact one-line rectangles."""
    fragments: StyleAndTextTuples = [("", f"{'›' if focused else ' '} {title} · ")]
    for index, option in enumerate(state.options):
        selected = option.uid == state.selected_uid
        visual = choice_visual_state(
            cursor=selected,
            selected=selected,
            focused=focused,
        )
        fragments.extend(
            [
                (visual.border_style, "["),
                (
                    visual.content_style,
                    f" {choice_marker(selected=selected)} "
                    f"{display_escape_text(option.label)} ",
                ),
                (visual.border_style, "]"),
            ]
        )
        if index < len(state.options) - 1:
            fragments.append(("", "  "))
    fragments.append(("", " · ←/→ TO SELECT"))
    selected = state.options[state.selected_index]
    if show_description and selected.description:
        fragments.extend(
            [
                ("", "\n"),
                ("", f"  MEANING · {display_escape_text(selected.description)}"),
            ]
        )
    return fragments


def _render_boxed_horizontal_choice(
    state: HorizontalChoiceState,
    *,
    title: str,
    focused: bool,
    show_description: bool,
) -> StyleAndTextTuples:
    """Render the shared choice state as individually focused cards."""
    fragments: StyleAndTextTuples = [
        ("", f"{'›' if focused else ' '} {title} · ←/→ SELECT\n  ")
    ]
    cards = []
    for option in state.options:
        label = display_escape_text(option.label)
        selected = option.uid == state.selected_uid
        cards.append(
            render_choice_card_rows(
                (f" {choice_marker(selected=selected)} {label} ",),
                visual=choice_visual_state(
                    cursor=selected,
                    selected=selected,
                    focused=focused,
                ),
            )
        )
    for row_index in range(3):
        for index, card in enumerate(cards):
            fragments.extend(card[row_index])
            if index < len(cards) - 1:
                fragments.append(("", "  "))
        if row_index != 2:
            fragments.append(("", "\n  "))
    selected = state.options[state.selected_index]
    if show_description and selected.description:
        fragments.extend(
            [
                ("", "\n"),
                ("", f"  MEANING · {display_escape_text(selected.description)}"),
            ]
        )
    return fragments
