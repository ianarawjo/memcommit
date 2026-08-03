"""Small terminal picker for selecting one Context by name."""
from __future__ import annotations

import sys
from collections.abc import Sequence

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style


def _render_context_options(
    options: Sequence[str],
    *,
    selected: int,
    current: str | None,
) -> list[tuple[str, str]]:
    """Render every option and anchor prompt-toolkit at the selected row."""
    fragments: list[tuple[str, str]] = []
    for index, name in enumerate(options):
        is_selected = index == selected
        if is_selected:
            # A real cursor anchor lets Window own terminal-height-dependent
            # scrolling. Slicing to a fixed row count wastes tall terminals
            # and duplicates viewport logic already provided by prompt-toolkit.
            fragments.append(("[SetCursorPosition]", ""))
        is_current = name == current
        style = "class:selected" if is_selected else ""
        pointer = "›" if is_selected else " "
        active = "*" if is_current else " "
        fragments.append((style, f"{pointer} {active} {name}"))
        if index < len(options) - 1:
            fragments.append(("", "\n"))
    return fragments


def choose_context(
    names: Sequence[str],
    *,
    current: str | None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Return the selected Context name, or ``None`` when cancelled."""
    options = tuple(names)
    if not options:
        raise ValueError("No contexts are available to select.")
    if (
        any(not isinstance(name, str) or not name for name in options)
        or len(set(options)) != len(options)
    ):
        raise ValueError("Context selection received invalid names.")
    if require_tty and (
        not sys.stdin.isatty() or not sys.stdout.isatty()
    ):
        raise ValueError(
            "Interactive context selection requires a terminal. "
            "Pass a Context name explicitly."
        )

    selected = {
        "index": options.index(current) if current in options else 0,
    }
    bindings = KeyBindings()

    def render_options():
        return _render_context_options(
            options,
            selected=selected["index"],
            current=current,
        )

    control = FormattedTextControl(
        text=render_options,
        focusable=True,
        show_cursor=False,
    )

    def move(delta: int) -> None:
        selected["index"] = max(
            0,
            min(selected["index"] + delta, len(options) - 1),
        )

    @bindings.add("down")
    def _next_context(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up")
    def _previous_context(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("enter")
    def _accept_context(event) -> None:
        event.app.exit(result=options[selected["index"]])

    @bindings.add("q", eager=True)
    @bindings.add("escape")
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(" Select a Context"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                " ↑/↓ move  Enter switch  Esc/q cancel"
                f"  ·  {selected['index'] + 1}/{len(options)}"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[str | None] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    Window(height=1, char="─"),
                    options_window,
                    Window(height=1, char="─"),
                    footer,
                ]
            ),
            focused_element=control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=Style.from_dict(
            {
                "selected": "reverse bold",
            }
        ),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
