"""Shared Help handoff contracts for long-lived terminal sessions."""

from __future__ import annotations

import threading

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.widgets import TextArea

from memcommit.commands.help_inventory.command import CommandEntry
from memcommit.commands.shared.session_help import SessionHelpController


def _entries() -> tuple[CommandEntry, ...]:
    return (
        CommandEntry(
            name="query",
            annotation=None,
            description="Ask across readable Contexts.",
            command=object(),
            forms=("mem query", "mem query [question]"),
        ),
    )


def test_h_opens_and_h_hides_help_then_restores_the_parent_focus():
    opened = threading.Event()
    closed = threading.Event()
    returned = threading.Event()
    actions: list[tuple[str, str | None]] = []
    bindings = KeyBindings()
    body_control = FormattedTextControl("SESSION", focusable=True)

    def observe(action: str, command_name: str | None) -> None:
        actions.append((action, command_name))
        if action == "OPEN":
            opened.set()
        elif action == "CLOSE":
            closed.set()

    def return_to_parent(application: Application) -> None:
        assert application.layout.current_control is body_control
        returned.set()
        application.invalidate()

    with create_pipe_input() as pipe_input:
        controller = SessionHelpController(
            entries=_entries(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            on_action=observe,
            on_closed=return_to_parent,
        )
        controller.bind(bindings)

        @bindings.add("q", eager=True)
        def close_parent(event) -> None:
            event.app.exit(result="closed")

        application: Application[str] = Application(
            layout=Layout(Window(body_control), focused_element=body_control),
            key_bindings=bindings,
            full_screen=True,
            input=pipe_input,
            output=DummyOutput(),
        )

        def drive() -> None:
            pipe_input.send_text("H")
            if not opened.wait(3):
                pipe_input.send_text("\x03")
                return
            pipe_input.send_text("h")
            if not closed.wait(3) or not returned.wait(3):
                pipe_input.send_text("\x03")
                return
            pipe_input.send_text("q")

        driver = threading.Thread(target=drive, daemon=True)
        driver.start()
        assert application.run() == "closed"
        driver.join(timeout=3)

    assert not driver.is_alive()
    assert actions == [
        ("OPEN", None),
        ("HIDE", None),
        ("CLOSE", None),
    ]
    assert not controller.is_open


def test_h_remains_text_while_a_writable_field_has_focus():
    bindings = KeyBindings()
    input_area = TextArea(multiline=False)
    controller = SessionHelpController(entries=_entries())
    controller.bind(bindings, filter=~has_focus(input_area))

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    def submit(event) -> None:
        event.app.exit(result=input_area.text)

    with create_pipe_input() as pipe_input:
        application: Application[str] = Application(
            layout=Layout(input_area, focused_element=input_area),
            key_bindings=bindings,
            full_screen=True,
            input=pipe_input,
            output=DummyOutput(),
        )
        pipe_input.send_text("hH\r")
        result = application.run()

    assert result == "hH"
    assert not controller.is_open
