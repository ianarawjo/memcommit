"""Private terminal capture for interactive, line-oriented Memory intake."""

from __future__ import annotations

import sys

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output


class PasteCancelled(Exception):
    """Raised when the user cancels interactive paste capture."""


def _non_empty_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def capture_paste(
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str:
    """
    Capture pasted text without rendering the payload itself.

    Bracketed-paste events arrive as one value, so the display can report only
    a line count.  Printable keystrokes are also accepted as a conservative
    fallback, but neither path inserts the payload into the rendered control.
    """
    if require_tty and (
        not sys.stdin.isatty() or not sys.stdout.isatty()
    ):
        raise ValueError(
            "--paste requires an interactive terminal. "
            "For piped input, use --input -."
        )

    fragments: list[str] = []
    bindings = KeyBindings()

    def append(text: str) -> None:
        fragments.append(text)

    def captured_text() -> str:
        return "".join(fragments)

    @bindings.add(Keys.BracketedPaste, eager=True)
    def _accept_bracketed_paste(event) -> None:
        text = event.data.replace("\r\n", "\n").replace("\r", "\n")
        existing = captured_text()
        if (
            existing
            and text
            and not existing.endswith("\n")
            and not text.startswith("\n")
        ):
            # Separate independently pasted blocks so their boundary does not
            # silently fuse two intended Memory lines.
            append("\n")
        append(text)
        event.app.invalidate()

    @bindings.add("enter")
    @bindings.add("c-j")
    def _accept_newline(event) -> None:
        append("\n")
        event.app.invalidate()

    @bindings.add("tab")
    def _accept_tab(event) -> None:
        append("\t")
        event.app.invalidate()

    @bindings.add("backspace")
    def _delete_last_character(event) -> None:
        text = captured_text()
        fragments[:] = [text[:-1]] if text else []
        event.app.invalidate()

    @bindings.add("c-d", eager=True)
    @bindings.add(Keys.F2, eager=True)
    def _finish(event) -> None:
        event.app.exit(result=captured_text())

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    @bindings.add(Keys.Any)
    def _accept_printable_character(event) -> None:
        if event.data and all(character.isprintable() for character in event.data):
            append(event.data)
            event.app.invalidate()

    def render_status():
        count = _non_empty_line_count(captured_text())
        noun = "line" if count == 1 else "lines"
        status = (
            f"[{count} {noun} pasted]  "
            f"F2/Ctrl-D: review  Esc/Ctrl-C: cancel"
        )
        return [
            (
                "",
                "Paste text; each non-empty line becomes one Memory.\n",
            ),
            ("", status),
        ]

    control = FormattedTextControl(
        text=render_status,
        focusable=True,
        show_cursor=False,
    )
    app = Application(
        layout=Layout(
            Window(
                control,
                height=Dimension.exact(2),
                dont_extend_height=True,
                wrap_lines=False,
            )
        ),
        key_bindings=bindings,
        full_screen=False,
        erase_when_done=True,
        input=app_input,
        output=app_output,
    )

    try:
        result = app.run()
    except (EOFError, KeyboardInterrupt) as error:
        raise PasteCancelled from error
    if result is None:
        raise PasteCancelled
    return result
