"""Compact Source-and-name setup for interactive Context branching."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output

from memcommit.commands.tui_primitives import (
    ExactNameFieldView,
    ExactNameInputControl,
    MEMCOMMIT_TUI_STYLE,
    build_focused_frame,
    display_escape_text,
    focus_in_order,
    focused_control_style,
    safe_terminal_text,
)
from memcommit.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)


@dataclass(frozen=True)
class BranchCreationReceipt:
    """One process-local Source and exact require-new branch name."""

    source_name: str
    new_name: str


def choose_branch_creation(
    local_names: Sequence[str],
    *,
    current: str | None,
    suggest_name: Callable[[str], str],
    validate_name: Callable[[str], None],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> BranchCreationReceipt | None:
    """Choose one ordinary local Source and edit one exact new Context name."""

    names = tuple(local_names)
    if not names or len(set(names)) != len(names):
        raise ValueError("Interactive Branch requires ordinary local Contexts.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive Branch creation requires a terminal. Pass a name explicitly."
        )
    initial_source = current if current in names else names[0]
    source = ContextSelectorControl(
        ContextSelectorView(
            names=names,
            selected=(initial_source,),
            label="FROM CONTEXT",
            current_context=current,
        ),
        height=4,
    )
    initial_suggestion = suggest_name(initial_source)
    name = ExactNameInputControl.create(
        ExactNameFieldView(
            value=initial_suggestion,
            label="NEW CONTEXT NAME",
            state="NOT CREATED",
            detail="Enter creates this exact branch Context and switches to it.",
            validate=validate_name,
            value_label="Context name",
        ),
        input_name="branch-context-name",
    )
    suggested = {"value": initial_suggestion}
    status = {"value": ""}
    bindings = KeyBindings()
    source_focus = has_focus(source.control)

    def set_status(value: object = "") -> None:
        status["value"] = display_escape_text(str(value)) if value else ""

    def refresh_suggestion(selected_source: str) -> None:
        previous = suggested["value"]
        candidate = suggest_name(selected_source)
        suggested["value"] = candidate
        # Source navigation must not overwrite an exact draft the person has
        # already edited away from the last visible suggestion.
        if name.text == previous:
            name.set_text(candidate)

    @bindings.add("up", filter=source_focus, eager=True)
    def _source_up(event) -> None:
        source.move(-1)
        set_status()
        event.app.invalidate()

    @bindings.add("down", filter=source_focus, eager=True)
    def _source_down(event) -> None:
        before = source.tree.selected_name
        source.move(1)
        if source.tree.selected_name == before:
            event.app.layout.focus(name.input)
        set_status()
        event.app.invalidate()

    @bindings.add("left", filter=source_focus, eager=True)
    def _source_left(event) -> None:
        source.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=source_focus, eager=True)
    def _source_right(event) -> None:
        source.expand()
        event.app.invalidate()

    @bindings.add("a", filter=source_focus, eager=True)
    @bindings.add("A", filter=source_focus, eager=True)
    def _source_expand_all(event) -> None:
        source.toggle_expand_all()
        event.app.invalidate()

    @bindings.add("enter", filter=source_focus, eager=True)
    @bindings.add(" ", filter=source_focus, eager=True)
    def _choose_source(event) -> None:
        try:
            source.choose_cursor()
        except ValueError as error:
            set_status(error)
            event.app.invalidate()
            return
        refresh_suggestion(source.selection.selected_name)
        event.app.layout.focus(name.input)
        set_status(
            f"Source selected · {source.selection.selected_name} · edit the branch name."
        )
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(name.input), eager=True)
    def _submit(event) -> None:
        try:
            candidate = name.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            set_status(error)
            event.app.invalidate()
            return
        event.app.exit(
            result=BranchCreationReceipt(
                source_name=source.selection.selected_name,
                new_name=candidate,
            )
        )

    @bindings.add("up", filter=has_focus(name.input), eager=True)
    def _return_to_source(event) -> None:
        event.app.layout.focus(source.control)
        set_status()
        event.app.invalidate()

    @bindings.add("tab")
    @bindings.add("s-tab")
    def _cycle(event) -> None:
        controls = (source.control, name.input)
        delta = -1 if event.key_sequence[0].key == Keys.BackTab else 1
        focus_in_order(event.app, controls, delta, wrap=True)
        set_status()
        event.app.invalidate()

    @bindings.add("c-j", filter=has_focus(name.input), eager=True)
    def _reject_newline(event) -> None:
        set_status("Context names stay on one line.")
        event.app.invalidate()

    @bindings.add("q", filter=source_focus, eager=True)
    @bindings.add("escape", filter=source_focus | has_focus(name.input), eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def header_text() -> str:
        return (
            " MEM BRANCH · SOURCE UNCHANGED\n "
            f"{display_escape_text(source.selection.selected_name)} → "
            f"{display_escape_text(name.text.strip())} · NOT CREATED"
        )

    def footer_text() -> FormattedText:
        if status["value"]:
            return FormattedText([("class:error", f" {status['value']}")])
        return FormattedText(
            [
                (
                    "",
                    " ↑/↓ move · Tab/Shift-Tab section · Enter choose/create · Ctrl-U clear · Esc cancel",
                )
            ]
        )

    def branch_frame_focused() -> bool:
        app = get_app()
        return app.layout.has_focus(source.control) or app.layout.has_focus(name.input)

    def new_name_label() -> FormattedText:
        focused = get_app().layout.has_focus(name.input)
        return FormattedText(
            [
                ("", "  NEW · "),
                (
                    focused_control_style(focused=focused, selected=focused),
                    "[ NEW CONTEXT NAME ]",
                ),
                ("", " · NOT CREATED"),
            ]
        )

    branch_frame = build_focused_frame(
        HSplit(
            [
                Window(
                    source.control,
                    height=Dimension.exact(4),
                    wrap_lines=False,
                    right_margins=[ScrollbarMargin(display_arrows=True)],
                ),
                Window(height=Dimension.exact(1), char="─"),
                Window(
                    FormattedTextControl(new_name_label),
                    height=Dimension.exact(1),
                    dont_extend_height=True,
                ),
                name.input,
            ]
        ),
        title=safe_terminal_text("FROM CONTEXT → NEW CONTEXT"),
        is_focused=branch_frame_focused,
        height=Dimension.exact(9),
    )

    root = HSplit(
        [
            Window(
                FormattedTextControl(header_text),
                height=Dimension.exact(2),
                dont_extend_height=True,
            ),
            branch_frame,
            Window(
                FormattedTextControl(footer_text),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
        ],
        height=Dimension.exact(12),
    )
    app: Application[BranchCreationReceipt | None] = Application(
        layout=Layout(root, focused_element=name.input),
        key_bindings=bindings,
        full_screen=False,
        mouse_support=False,
        style=MEMCOMMIT_TUI_STYLE,
        input=app_input,
        output=app_output,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
