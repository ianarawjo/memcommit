"""Small process-local left/right choice presentation for terminal shells."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.tui_primitives import (
    display_escape_text,
    focused_control_style,
)


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
    fragments: StyleAndTextTuples = [
        ("", f"{'›' if focused else ' '} {title} · ")
    ]
    for index, option in enumerate(state.options):
        selected = option.uid == state.selected_uid
        fragments.append(
            (
                focused_control_style(
                    focused=focused and selected,
                    selected=selected,
                ),
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
    fragments: StyleAndTextTuples = [
        ("", f"{'›' if focused else ' '} {title} · ")
    ]
    for index, option in enumerate(state.options):
        selected = option.uid == state.selected_uid
        keyboard_target = focused and selected
        border_style = (
            "class:memcommit.choice.border.focused" if keyboard_target else ""
        )
        content_style = focused_control_style(
            focused=keyboard_target,
            selected=selected,
        )
        fragments.extend(
            [
                (border_style, "["),
                (
                    content_style,
                    f" {'✓ ' if selected else '  '}"
                    f"{display_escape_text(option.label)} ",
                ),
                (border_style, "]"),
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
    escaped_labels = tuple(
        display_escape_text(option.label) for option in state.options
    )
    fragments: StyleAndTextTuples = [
        ("", f"{'›' if focused else ' '} {title} · ←/→ SELECT\n  ")
    ]
    for row in ("top", "middle", "bottom"):
        for index, (option, label) in enumerate(zip(state.options, escaped_labels)):
            selected = option.uid == state.selected_uid
            keyboard_target = focused and selected
            choice_text = f"{'✓ ' if selected else '  '}{label}"
            border_style = (
                "class:memcommit.choice.border.focused"
                if keyboard_target
                else ""
            )
            content_style = focused_control_style(
                focused=keyboard_target,
                selected=selected,
            )
            horizontal = "━" if keyboard_target else "─"
            vertical = "┃" if keyboard_target else "│"
            if row == "top":
                left, content, right = (
                    ("┏", horizontal * (len(label) + 4), "┓")
                    if keyboard_target
                    else ("┌", horizontal * (len(label) + 4), "┐")
                )
                fragments.append((border_style, left + content + right))
            elif row == "middle":
                fragments.extend(
                    [
                        (border_style, vertical),
                        (content_style, f" {choice_text} "),
                        (border_style, vertical),
                    ]
                )
            else:
                left, content, right = (
                    ("┗", horizontal * (len(label) + 4), "┛")
                    if keyboard_target
                    else ("└", horizontal * (len(label) + 4), "┘")
                )
                fragments.append((border_style, left + content + right))
            if index < len(state.options) - 1:
                fragments.append(("", "  "))
        if row != "bottom":
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
