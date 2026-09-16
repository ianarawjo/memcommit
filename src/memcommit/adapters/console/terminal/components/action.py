"""Compact read-only action labels; operation adapters own validation and execution."""

from collections.abc import Callable

from prompt_toolkit.application import get_app
from prompt_toolkit.layout import FormattedTextControl

from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    focused_control_style,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text


def build_action_control(
    label: str, *, describe: Callable[[], str] | None = None
) -> FormattedTextControl:
    """Render one focusable action with optional neutral, operation-owned effects."""

    def render():
        focused = get_app().layout.has_focus(control)
        fragments = []
        if describe is not None:
            fragments.append(
                ("class:report-neutral", f" {safe_terminal_text(describe())}\n")
            )
        fragments.append(
            (
                focused_control_style(focused=focused, selected=focused),
                f"{'›' if focused else ' '} [ {safe_terminal_text(label)} ]",
            )
        )
        return fragments

    control = FormattedTextControl(render, focusable=True, show_cursor=False)
    return control
