"""Contracts for the interactive whole-store Profile selector."""
from __future__ import annotations

import threading

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.commands.profile_picker as profile_picker_module
from memcommit.commands.profile_picker import (
    ProfilePickerAction,
    ProfilePickerEntry,
    ProfilePickerRefresh,
    _picker_rows,
    _removal_action,
    _removal_review,
    _render_profile_options,
    choose_profile,
)


ENTRIES = (
    ProfilePickerEntry(
        name="authoring",
        context_count=20,
        memory_count=240,
        current_context="test/update/to",
    ),
    ProfilePickerEntry(
        name="task-1",
        context_count=14,
        memory_count=375,
        current_context="participant/construction-updates",
        granted_context_count=2,
        granted_memory_count=12,
        query_source_count=1,
        query_source_names=("construction-details",),
    ),
    ProfilePickerEntry(
        name="task-2",
        context_count=34,
        memory_count=300,
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
    assert "Contexts 14 owned + 2 granted" in lines[1]
    assert "Memories 375 owned + 12 granted" in lines[1]
    assert "query=construction-details" in lines[1]
    assert lines[1].index("query=construction-details") < lines[1].index(
        "current="
    )
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

    assert selected == ProfilePickerAction(
        kind="USE",
        name="task-1",
        uid=None,
        registry_generation=None,
    )


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

    assert selected == ProfilePickerAction(
        kind="USE",
        name="task-1",
        uid=None,
        registry_generation=None,
    )


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


def test_profile_picker_nests_study_task_profiles_under_timestamped_heading():
    entries = (
        ENTRIES[0],
        ProfilePickerEntry(
            name="pilot-001-task-1",
            context_count=14,
            memory_count=375,
            current_context="participant/construction-updates",
            study_uid="study-pilot-001",
            study_name="pilot-001",
            study_created_at="2026-08-03T20:34:05+00:00",
            study_task=1,
            study_profile_count=3,
        ),
        ProfilePickerEntry(
            name="pilot-001-task-2",
            context_count=34,
            memory_count=300,
            current_context="advisor1",
            study_uid="study-pilot-001",
            study_name="pilot-001",
            study_created_at="2026-08-03T20:34:05+00:00",
            study_task=2,
            study_profile_count=3,
        ),
        ProfilePickerEntry(
            name="pilot-001-task-3",
            context_count=42,
            memory_count=375,
            current_context="personal-memory",
            study_uid="study-pilot-001",
            study_name="pilot-001",
            study_created_at="2026-08-03T20:34:05+00:00",
            study_task=3,
            study_profile_count=3,
        ),
    )

    rendered = _visible_text(
        _render_profile_options(entries, selected=3, current="authoring")
    )

    lines = rendered.splitlines()
    assert len(lines) == 5
    assert lines[1] == (
        "  STUDY pilot-001 · 3 active · created=2026-08-03T20:34:05+00:00"
    )
    assert "Task 1 · pilot-001-task-1" in lines[2]
    assert "Task 2 · pilot-001-task-2" in lines[3]
    assert "USE" in lines[3]
    assert "Task 3 · pilot-001-task-3" in lines[4]


def test_profile_picker_keeps_study_authorities_with_their_tasks():
    entries = (
        ProfilePickerEntry(
            name="authoring",
            context_count=1,
            current_context="inbox",
        ),
        ProfilePickerEntry(
            name="pilot-001-task-1",
            context_count=1,
            current_context="task",
            study_uid="study-pilot-001",
            study_name="pilot-001",
            study_created_at="2026-08-03T20:34:05+00:00",
            study_task=1,
            study_role="TASK",
            study_profile_count=3,
        ),
        ProfilePickerEntry(
            name="pilot-001-task-1-campus-authority",
            context_count=1,
            current_context="campus",
            study_uid="study-pilot-001",
            study_name="pilot-001",
            study_created_at="2026-08-03T20:34:05+00:00",
            study_task=1,
            study_role="AUTHORITY",
            study_profile_count=3,
        ),
        ProfilePickerEntry(
            name="pilot-001-task-2",
            context_count=1,
            current_context="proposal",
            study_uid="study-pilot-001",
            study_name="pilot-001",
            study_created_at="2026-08-03T20:34:05+00:00",
            study_task=2,
            study_role="TASK",
            study_profile_count=3,
        ),
    )

    rendered = _visible_text(
        _render_profile_options(entries, selected=3, current="authoring")
    )

    assert rendered.count("STUDY pilot-001") == 1
    assert "Task 1 · pilot-001-task-1" in rendered
    assert "Authority 1 · pilot-001-task-1-campus-authority" in rendered
    assert "Task 2 · pilot-001-task-2" in rendered


def test_profile_picker_labels_current_init_study_pair():
    entries = (
        ENTRIES[0],
        ProfilePickerEntry(
            name="pilot-current",
            context_count=65,
            memory_count=457,
            current_context="task-1/participant",
            study_uid="study-pilot-current",
            study_name="pilot-current",
            study_created_at="2026-08-09T20:34:05+00:00",
            study_role="PARTICIPANT",
            study_profile_count=2,
        ),
        ProfilePickerEntry(
            name="renamed-authority",
            context_count=75,
            memory_count=625,
            current_context="task-1/campus-wiki",
            study_uid="study-pilot-current",
            study_name="pilot-current",
            study_created_at="2026-08-09T20:34:05+00:00",
            study_role="GRANTED_MEMORY",
            study_profile_count=2,
        ),
    )

    rendered = _visible_text(
        _render_profile_options(entries, selected=2, current="pilot-current")
    )

    assert rendered.count("STUDY pilot-current") == 1
    assert "Participant · pilot-current" in rendered
    assert "Granted memory · renamed-authority" in rendered


def test_profile_picker_focuses_study_header_as_its_own_row():
    entries = (
        ENTRIES[0],
        ProfilePickerEntry(
            name="pilot-participant",
            uid="participant-uid",
            context_count=2,
            current_context="practice",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="PARTICIPANT",
            study_profile_count=2,
        ),
        ProfilePickerEntry(
            name="pilot-authority",
            uid="authority-uid",
            context_count=3,
            current_context="source",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="GRANTED_MEMORY",
            study_profile_count=2,
        ),
    )

    rendered = _visible_text(
        _render_profile_options(entries, selected=1, current="authoring")
    )

    assert rendered.splitlines()[1].startswith("› STUDY pilot")
    assert "USE" not in rendered.splitlines()[1]


def test_profile_picker_study_header_d_then_enter_returns_whole_study_action():
    entries = (
        ENTRIES[0],
        ProfilePickerEntry(
            name="pilot-participant",
            uid="participant-uid",
            context_count=2,
            current_context="practice",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="PARTICIPANT",
            study_profile_count=2,
        ),
        ProfilePickerEntry(
            name="pilot-authority",
            uid="authority-uid",
            context_count=3,
            current_context="source",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="GRANTED_MEMORY",
            study_profile_count=2,
        ),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Bd\r")
        selected = choose_profile(
            entries,
            current="authoring",
            registry_generation=7,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == ProfilePickerAction(
        kind="REMOVE_STUDY",
        name="pilot",
        uid="study-uid",
        registry_generation=7,
    )


def test_profile_picker_deletion_cycles_every_shared_busy_frame(monkeypatch):
    entries = (
        ENTRIES[0],
        ProfilePickerEntry(
            name="pilot-participant",
            uid="participant-uid",
            context_count=2,
            current_context="practice",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="PARTICIPANT",
            study_profile_count=2,
        ),
        ProfilePickerEntry(
            name="pilot-authority",
            uid="authority-uid",
            context_count=3,
            current_context="source",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="GRANTED_MEMORY",
            study_profile_count=2,
        ),
    )
    original_suffix = profile_picker_module.busy_suffix
    rendered_frames: set[str] = set()
    all_frames_rendered = threading.Event()
    deletion_started = threading.Event()
    release_deletion = threading.Event()
    feeder_errors: list[Exception] = []

    def capture_suffix(frame_index: int) -> str:
        suffix = original_suffix(frame_index)
        rendered_frames.add(suffix)
        if rendered_frames == {".", "..", "…"}:
            all_frames_rendered.set()
        return suffix

    monkeypatch.setattr(profile_picker_module, "busy_suffix", capture_suffix)
    monkeypatch.setattr(
        profile_picker_module,
        "_PROFILE_DELETION_BUSY_INTERVAL_SECONDS",
        0.01,
    )

    def delete(_action: ProfilePickerAction) -> str:
        deletion_started.set()
        if not release_deletion.wait(2):
            raise RuntimeError("test did not release deletion")
        return "Deletion completed"

    with create_pipe_input() as pipe_input:

        def release_after_animation() -> None:
            try:
                pipe_input.send_text("\x1b[Bd\r")
                if not deletion_started.wait(2):
                    raise AssertionError("deletion did not start")
                if not all_frames_rendered.wait(2):
                    raise AssertionError("busy indicator did not animate")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
            finally:
                release_deletion.set()

        feeder = threading.Thread(target=release_after_animation)
        feeder.start()
        selected = choose_profile(
            entries,
            current="authoring",
            registry_generation=9,
            apply_removal=delete,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert rendered_frames == {".", "..", "…"}
    assert selected == ProfilePickerRefresh(status="Deletion completed")


def test_profile_picker_review_warns_that_store_and_checkpoints_are_unrecoverable():
    entries = (
        ENTRIES[0],
        ProfilePickerEntry(
            name="pilot-participant",
            uid="participant-uid",
            context_count=2,
            current_context="practice",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="PARTICIPANT",
            study_profile_count=2,
        ),
        ProfilePickerEntry(
            name="pilot-authority",
            uid="authority-uid",
            context_count=3,
            current_context="source",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="GRANTED_MEMORY",
            study_profile_count=2,
        ),
    )
    row = _picker_rows(entries, current="authoring")[1]
    action = _removal_action(row, registry_generation=9)

    review = _removal_review(action, row)

    assert any("Memory, session, and checkpoint" in line for line in review.effects)
    assert "This cannot be undone or recovered by mem." in review.effects


def test_profile_picker_child_d_then_a_returns_only_profile_action():
    entries = (
        ENTRIES[0],
        ProfilePickerEntry(
            name="pilot-participant",
            uid="participant-uid",
            context_count=2,
            current_context="practice",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="PARTICIPANT",
            study_profile_count=2,
        ),
        ProfilePickerEntry(
            name="pilot-authority",
            uid="authority-uid",
            context_count=3,
            current_context="source",
            study_uid="study-uid",
            study_name="pilot",
            study_created_at="2026-08-13T10:00:00+00:00",
            study_role="GRANTED_MEMORY",
            study_profile_count=2,
        ),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\x1b[Bda")
        selected = choose_profile(
            entries,
            current="authoring",
            registry_generation=8,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == ProfilePickerAction(
        kind="REMOVE_PROFILE",
        name="pilot-participant",
        uid="participant-uid",
        registry_generation=8,
    )


def test_profile_picker_escape_returns_from_review_without_applying():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Bd\x1bq")
        selected = choose_profile(
            ENTRIES,
            current="authoring",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None
