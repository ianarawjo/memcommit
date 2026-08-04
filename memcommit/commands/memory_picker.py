"""Shared read-only terminal picker for trace/rationale Memory selection."""
from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style

from memcommit.commands.tui_primitives import display_escape_text


MemoryPickerOperation = Literal["trace", "rationale"]


@runtime_checkable
class MemoryPickerItem(Protocol):
    """Minimal presentation projection supplied by provenance."""

    uid: str
    content: str
    status: Literal["CURRENT", "HISTORICAL"]


def _preview(value: str, limit: int = 100) -> str:
    escaped = display_escape_text(value)
    return escaped if len(escaped) <= limit else escaped[: limit - 1] + "…"


def _render_memory_options(
    options: Sequence[MemoryPickerItem],
    *,
    selected: int,
):
    """Render all rows and anchor prompt-toolkit at the selected Memory."""
    fragments: list[tuple[str, str]] = []
    for index, item in enumerate(options):
        is_selected = index == selected
        if is_selected:
            # The cursor marker lets Window scroll with the terminal height
            # without maintaining a second fixed-size viewport in this module.
            fragments.append(("[SetCursorPosition]", ""))
        style = "class:selected" if is_selected else ""
        pointer = "›" if is_selected else " "
        fragments.append(
            (
                style,
                f"{pointer} {item.status:<10} "
                f"[{display_escape_text(item.uid[:8])}]  "
                f"{_preview(item.content)}",
            )
        )
        if index < len(options) - 1:
            fragments.append(("", "\n"))
    return fragments


def choose_memory(
    items: Sequence[MemoryPickerItem],
    *,
    context_name: str,
    operation: MemoryPickerOperation,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Return one exact Memory UID, or ``None`` when selection is cancelled."""
    options = tuple(items)
    if operation not in {"trace", "rationale"}:
        raise ValueError("Memory picker operation must be trace or rationale.")
    if not isinstance(context_name, str) or not context_name:
        raise ValueError("Memory selection requires a Context name.")
    if not options:
        raise ValueError(
            "No current or retained historical direct Memories are available."
        )
    if any(
        not isinstance(item.uid, str)
        or not item.uid
        or not isinstance(item.content, str)
        or item.status not in {"CURRENT", "HISTORICAL"}
        for item in options
    ):
        raise ValueError("Memory selection received an invalid entry.")
    if len({item.uid for item in options}) != len(options):
        raise ValueError("Memory selection received duplicate UIDs.")
    if require_tty and (
        not sys.stdin.isatty() or not sys.stdout.isatty()
    ):
        raise ValueError(
            "Interactive Memory selection requires a terminal. "
            "Pass a Memory UID explicitly."
        )

    selected = {"index": 0}
    bindings = KeyBindings()

    def move(delta: int) -> None:
        selected["index"] = max(
            0,
            min(selected["index"] + delta, len(options) - 1),
        )

    def render_options():
        return _render_memory_options(
            options,
            selected=selected["index"],
        )

    def render_detail() -> str:
        item = options[selected["index"]]
        scope = (
            "full retained lineage · earliest evidence → current Context"
            if operation == "trace"
            else "recorded evidence + saved analysis + current interpretation"
        )
        return (
            f" Selected · {item.status} · {display_escape_text(item.uid)}\n"
            f" Scope · {scope}\n"
            f" {display_escape_text(item.content)}"
        )

    control = FormattedTextControl(
        text=render_options,
        focusable=True,
        show_cursor=False,
    )

    @bindings.add("down")
    def _next_memory(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up")
    def _previous_memory(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("pagedown")
    def _page_down(event) -> None:
        move(10)
        event.app.invalidate()

    @bindings.add("pageup")
    def _page_up(event) -> None:
        move(-10)
        event.app.invalidate()

    @bindings.add("home")
    def _first_memory(event) -> None:
        selected["index"] = 0
        event.app.invalidate()

    @bindings.add("end")
    def _last_memory(event) -> None:
        selected["index"] = len(options) - 1
        event.app.invalidate()

    @bindings.add("enter")
    def _accept_memory(event) -> None:
        event.app.exit(result=options[selected["index"]].uid)

    @bindings.add("q", eager=True)
    @bindings.add("escape")
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    title = operation.upper()
    header = Window(
        FormattedTextControl(
            f" {title} · SELECT A MEMORY · {display_escape_text(context_name)}"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    detail = Window(
        FormattedTextControl(render_detail),
        height=Dimension(min=2, preferred=4, max=7),
        wrap_lines=True,
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                " ↑/↓ move  PgUp/PgDn jump  Enter "
                + (
                    "full lineage"
                    if operation == "trace"
                    else "rationale layers"
                )
                + "  Esc/q cancel"
                + f"  ·  {selected['index'] + 1}/{len(options)}"
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
                    detail,
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
        style=Style.from_dict({"selected": "reverse bold"}),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
