"""Standalone exact-command approval surface for mutating setup flows."""

from __future__ import annotations

import sys

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.terminal.components.exact_command_review.interaction import (
    bind_exact_command_approval,
)
from memcommit.adapters.console.coordination.command_review.model import (
    CommandReview,
)
from memcommit.adapters.console.terminal.components.exact_command_review.rendering import (
    render_exact_command_review,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    build_scrollable_text_pane,
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.core.keybindings import bind_case_insensitive_key
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)


def approve_exact_command(
    review: CommandReview,
    *,
    title: str,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> bool:
    """Approve only the frozen argv shown on screen with Enter."""

    if not isinstance(review, CommandReview):
        raise TypeError("Exact-command approval requires a review receipt.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Exact-command approval title must be nonempty text.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive command approval requires a terminal.")

    bindings = KeyBindings()
    pane = build_scrollable_text_pane(
        "EXACT COMMAND · REVIEW BEFORE APPLY",
        render_exact_command_review(review),
        buffer_name="exact-command-review",
        style="class:report-neutral",
    )

    @bindings.add("down", eager=True)
    def _down(event) -> None:
        move_wrapped_read_cursor(event, direction=1)

    @bindings.add("up", eager=True)
    def _up(event) -> None:
        move_wrapped_read_cursor(event, direction=-1)

    @bindings.add("pagedown", eager=True)
    def _page_down(event) -> None:
        scroll_wrapped_page(event, direction=1)

    @bindings.add("pageup", eager=True)
    def _page_up(event) -> None:
        scroll_wrapped_page(event, direction=-1)

    @bind_exact_command_approval(bindings, eager=True)
    def _approve(event) -> None:
        event.app.exit(result=True)

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=False)

    header = Window(
        FormattedTextControl(
            [
                ("class:report-label", " " + safe_terminal_text(title) + "\n"),
                (
                    "class:report-neutral",
                    " Nothing has been applied. Enter applies only the command below.",
                ),
            ]
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    footer = Window(
        FormattedTextControl(
            " ↑/↓ scroll · Enter apply exact command · A also works · Esc/Q cancel"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[bool] = Application(
        layout=Layout(
            HSplit([header, pane.container, footer]),
            focused_element=pane.text_area,
        ),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        input=app_input,
        output=app_output,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return False
