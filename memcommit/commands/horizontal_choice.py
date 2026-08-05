"""Small process-local left/right choice presentation for terminal shells."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.tui_primitives import display_escape_text


@dataclass(frozen=True)
class HorizontalChoiceOption:
    """One stable choice independent of an operation's semantic meaning."""

    uid: str
    label: str
    description: str = ""

    def __post_init__(self) -> None:
        if (
            not self.uid
            or not self.label
            or any(c in self.label for c in "\r\n")
            or any(c in self.description for c in "\r\n")
        ):
            raise ValueError("Horizontal choices require nonempty single-line values.")


@dataclass
class HorizontalChoiceState:
    """Immediate, reversible selection over a fixed ordered option set."""

    options: tuple[HorizontalChoiceOption, ...]
    selected_uid: str

    def __post_init__(self) -> None:
        uids = tuple(option.uid for option in self.options)
        if not uids or len(set(uids)) != len(uids):
            raise ValueError("Horizontal choices require distinct options.")
        if self.selected_uid not in uids:
            raise ValueError("The selected horizontal choice is unavailable.")

    @property
    def selected_index(self) -> int:
        return next(
            index
            for index, option in enumerate(self.options)
            if option.uid == self.selected_uid
        )

    def move(self, delta: int) -> bool:
        """Move without wrapping and report whether the value changed."""
        if isinstance(delta, bool) or not isinstance(delta, int):
            raise ValueError("Horizontal choice movement must be an integer.")
        index = max(0, min(self.selected_index + delta, len(self.options) - 1))
        selected_uid = self.options[index].uid
        changed = selected_uid != self.selected_uid
        self.selected_uid = selected_uid
        return changed


def render_horizontal_choice(
    state: HorizontalChoiceState,
    *,
    title: str,
    focused: bool,
    show_description: bool = False,
) -> StyleAndTextTuples:
    """Render one segmented row; callers retain all meaning and key bindings."""
    fragments: StyleAndTextTuples = [
        ("", f"{'›' if focused else ' '} {title} · ")
    ]
    for index, option in enumerate(state.options):
        selected = option.uid == state.selected_uid
        fragments.append(
            (
                "class:memcommit.choice.active" if selected else "",
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
