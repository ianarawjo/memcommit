"""Choose the local result Context for a reviewed symmetric Meld."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.commands.shared.tui_primitives import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.adapters.interfaces.tui.components.frame import (
    bind_focused_frame_style,
)
from memcommit.adapters.console.text import (
    display_escape_text,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class MeldTargetReceipt:
    """One exact target choice; creation still belongs to Meld orchestration."""

    context_name: str
    create: bool


def eligible_meld_targets(
    store: MemoryStore,
    *,
    source_names: tuple[str, str],
) -> tuple[str, ...]:
    """Return empty, local, session-free Contexts safe to offer as results."""
    result: list[str] = []
    for name in store.list_context_names():
        if name in source_names:
            continue
        context = store.load_direct(name)
        if tuple(context.iter_items()):
            continue
        if store.load_meld_session(context.uid) is not None:
            continue
        result.append(name)
    current = store.current_context_name()
    return tuple(
        sorted(
            result,
            key=lambda name: (name != current, name.casefold(), name),
        )
    )


def choose_meld_target(
    store: MemoryStore,
    *,
    source_names: tuple[str, str],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MeldTargetReceipt | None:
    """Choose an existing empty result or validate one new exact name."""
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Meld target selection requires a terminal.")
    existing = eligible_meld_targets(store, source_names=source_names)
    # A fresh result is the least surprising symmetric-Meld target. Existing
    # empty Contexts remain available, but never become the default merely
    # because their lexical name sorts first.
    rows = ("CREATE NEW RESULT CONTEXT", *existing)
    selected = {"index": 0}
    status = {"value": ""}
    bindings = KeyBindings()
    name_field = ExactNameFieldControl.create(
        ExactNameFieldView(
            value="",
            label="NEW RESULT CONTEXT",
            state="CREATE ON START",
            validate=store.assert_context_creatable,
            value_label="Context name",
        ),
        input_name="meld-result-context-name",
    )
    name_input = name_field.input

    def render_rows():
        fragments: list[tuple[str, str]] = []
        for index, value in enumerate(rows):
            active = index == selected["index"]
            if active:
                fragments.append(("[SetCursorPosition]", ""))
            marker = "›" if active else " "
            if index == 0:
                label = "+ NEW     CREATE NEW RESULT CONTEXT"
            else:
                value = existing[index - 1]
                current = " · CURRENT" if value == store.current_context_name() else ""
                label = f"  EMPTY   {display_escape_text(value)}{current}"
            fragments.append(("class:selected" if active else "", f"{marker} {label}"))
            if index < len(rows) - 1:
                fragments.append(("", "\n"))
        return fragments

    row_window = Window(
        FormattedTextControl(render_rows, focusable=True, show_cursor=False),
        wrap_lines=False,
    )
    name_frame = name_field.frame
    target_frame = Frame(row_window, title="RESULT TARGET")

    def move(delta: int) -> None:
        selected["index"] = max(0, min(selected["index"] + delta, len(rows) - 1))
        status["value"] = ""

    def open_name(event) -> None:
        name_field.set_text("")
        event.app.layout.focus(name_input)
        status["value"] = "Enter one exact new Context name."

    @bindings.add("down", filter=~has_focus(name_input))
    def _down(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=~has_focus(name_input))
    def _up(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("enter", filter=~has_focus(name_input))
    def _choose(event) -> None:
        if selected["index"] == 0:
            open_name(event)
            return
        event.app.exit(
            result=MeldTargetReceipt(existing[selected["index"] - 1], create=False)
        )

    @bindings.add("n", filter=~has_focus(name_input))
    def _new(event) -> None:
        selected["index"] = 0
        open_name(event)

    @bindings.add("enter", filter=has_focus(name_input), eager=True)
    def _submit_name(event) -> None:
        try:
            name = name_field.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
            event.app.invalidate()
            return
        event.app.exit(result=MeldTargetReceipt(name, create=True))

    @bindings.add("escape", filter=has_focus(name_input), eager=True)
    def _cancel_name(event) -> None:
        event.app.layout.focus(row_window)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("escape", filter=~has_focus(name_input), eager=True)
    @bind_case_insensitive_key(
        bindings, "q", filter=~has_focus(name_input), eager=True
    )
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(result=None)

    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {display_escape_text(status['value'])}"
                if status["value"]
                else " ↑/↓ move · Enter choose · N new Context · Esc/Q cancel"
            )
        ),
        height=Dimension.exact(1),
    )
    app: Application[MeldTargetReceipt | None] = Application(
        layout=Layout(
            HSplit(
                [
                    Window(
                        FormattedTextControl(
                            " MEM MELD · CHOOSE RESULT CONTEXT\n "
                            + display_escape_text(source_names[0])
                            + " + "
                            + display_escape_text(source_names[1])
                        ),
                        height=Dimension.exact(2),
                    ),
                    target_frame,
                    name_frame,
                    footer,
                ]
            ),
            focused_element=row_window,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=merge_styles(
            [MEMCOMMIT_TUI_STYLE, Style.from_dict({"selected": "reverse bold"})]
        ),
    )
    bind_focused_frame_style(
        target_frame,
        is_focused=lambda: not app.layout.has_focus(name_input),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
