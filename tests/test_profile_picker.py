"""Contracts for the interactive whole-store Profile selector."""
from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.profile_picker import (
    ProfilePickerEntry,
    _render_profile_options,
    choose_profile,
)


ENTRIES = (
    ProfilePickerEntry(
        name="authoring",
        context_count=20,
        current_context="test/update/to",
    ),
    ProfilePickerEntry(
        name="task-1",
        context_count=14,
        current_context="participant/construction-updates",
        query_source_count=1,
        query_source_names=("campus-wiki",),
    ),
    ProfilePickerEntry(
        name="task-2",
        context_count=34,
        current_context="advisor1",
        query_source_count=1,
        query_source_names=("proposal-guidelines",),
    ),
)


def _visible_text(fragments: list[tuple[str, str]]) -> str:
    return "".join(
        text for style, text in fragments if style != "[SetCursorPosition]"
    )


def test_profile_picker_marks_current_and_selected_use_action():
    rendered = _visible_text(
        _render_profile_options(ENTRIES, selected=1, current="authoring")
    )
    lines = rendered.splitlines()

    assert len(lines) == 3
    assert lines[0].startswith("  * authoring")
    assert "CURRENT" in lines[0]
    assert lines[1].startswith("›   task-1")
    assert "USE" in lines[1]
    assert "query=campus-wiki" in lines[1]
    assert lines[1].index("query=campus-wiki") < lines[1].index("current=")
    assert "USE" not in lines[2]


def test_profile_picker_preselects_current_and_accepts_enter():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_profile(
            ENTRIES,
            current="task-1",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "task-1"


def test_profile_picker_moves_and_returns_use_target():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        selected = choose_profile(
            ENTRIES,
            current="authoring",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "task-1"


def test_profile_picker_cancels_without_a_selection():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        selected = choose_profile(
            ENTRIES,
            current="authoring",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_profile_picker_renders_every_profile_for_window_owned_scrolling():
    entries = tuple(
        ProfilePickerEntry(
            name=f"study-{index:02}",
            context_count=index,
            current_context=None,
        )
        for index in range(30)
    )
    rendered = _visible_text(
        _render_profile_options(entries, selected=24, current="study-00")
    )

    assert len(rendered.splitlines()) == 30
    assert rendered.count("CURRENT") == 1
    assert rendered.count("USE") == 1


def test_profile_picker_anchors_viewport_at_exact_selected_profile():
    fragments = _render_profile_options(
        ENTRIES,
        selected=2,
        current="authoring",
    )
    cursor_markers = [
        index
        for index, fragment in enumerate(fragments)
        if fragment[0] == "[SetCursorPosition]"
    ]

    assert len(cursor_markers) == 1
    selected_fragment = fragments[cursor_markers[0] + 1]
    assert selected_fragment[0] == "class:selected"
    assert selected_fragment[1].startswith("›")
    assert "task-2" in selected_fragment[1]
