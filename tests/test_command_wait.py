"""Interactive shared waiting and read-only Help exploration contracts."""

from __future__ import annotations

import threading
import uuid

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.command_wait import (
    CommandWaitView,
    build_report_loading_view,
    run_command_wait,
)
from memcommit.commands.help_inventory import CommandEntry
from memcommit.profile_config import ProfileEntry
from memcommit.study_action_log import (
    StudyActionLedger,
    begin_study_action_recording,
    finish_study_action_recording,
    record_study_action,
)


def _entries() -> list[CommandEntry]:
    return [
        CommandEntry(
            name=name,
            annotation=None,
            description=f"{name} description",
            command=object(),
            forms=(f"mem {name}", f"mem {name} [value]"),
        )
        for name in ("add", "forget", "sever")
    ]


def _study_profile() -> ProfileEntry:
    return ProfileEntry(
        uid="22222222-2222-4222-8222-222222222222",
        name="study-wait",
        kind="MANAGED",
        source={
            "kind": "STUDY_RUN",
            "study_uid": "11111111-1111-4111-8111-111111111111",
            "study_name": "study-wait",
            "created_at": "2026-08-10T00:00:00+00:00",
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": "44444444-4444-4444-8444-444444444444",
            "baseline_profile_name": "study-baseline",
        },
    )


def test_report_is_default_and_h_toggles_help_without_restarting_work():
    help_opened = threading.Event()
    help_hidden = threading.Event()
    help_reopened = threading.Event()
    command_expanded = threading.Event()
    result_ready = threading.Event()
    actions: list[tuple[str, str | None]] = []
    open_count = 0

    def observe(action: str, command_name: str | None) -> None:
        nonlocal open_count
        actions.append((action, command_name))
        if action == "OPEN":
            open_count += 1
            (help_opened if open_count == 1 else help_reopened).set()
        elif action == "CLOSE" and open_count == 1:
            help_hidden.set()
        elif action == "EXPAND":
            command_expanded.set()
        elif action == "RESULT_READY":
            result_ready.set()

    def work(progress):
        progress.update("provider turn", step=2)
        if not command_expanded.wait(3):
            raise RuntimeError("Help was not explored while work was running.")
        return "completed result"

    with create_pipe_input() as pipe_input:
        def drive_terminal() -> None:
            # The report-shaped wait screen is the default. C toggles its
            # frozen inputs and H enters the optional Help layer.
            pipe_input.send_text("cch")
            if not help_opened.wait(3):
                pipe_input.send_text("\x03")
                return
            pipe_input.send_text("h")
            if not help_hidden.wait(3):
                pipe_input.send_text("\x03")
                return
            pipe_input.send_text("h")
            if not help_reopened.wait(3):
                pipe_input.send_text("\x03")
                return
            pipe_input.send_text("\r")
            if not result_ready.wait(3):
                pipe_input.send_text("q")
                return
            # Completion must not yank the participant out of Help. H returns
            # to the waiting operation and its ready result.
            pipe_input.send_text("h")

        driver = threading.Thread(target=drive_terminal, daemon=True)
        driver.start()
        result = run_command_wait(
            "SEVER",
            "freezing inputs",
            total=2,
            work=work,
            help_entries=_entries(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            interactive=True,
            interval=0.01,
            on_help_action=observe,
            return_view=CommandWaitView(
                title="SEVER REPORT · BUILDING",
                text="CONTENT PENDING · THIS IS NOT A RESULT",
            ),
            context_view=CommandWaitView(
                title="SEVER CONFIRMED INPUTS · READ-ONLY",
                text="SOURCE · frozen/source\nCRITERIA · frozen/criteria",
            ),
        )
        driver.join(timeout=3)

    assert result == "completed result"
    assert not driver.is_alive()
    first_open = actions.index(("OPEN", None))
    first_hide = actions.index(("HIDE", None))
    first_close = actions.index(("CLOSE", None))
    second_open = actions.index(("OPEN", None), first_open + 1)
    assert first_open < first_hide < first_close < second_open
    assert second_open < actions.index(("EXPAND", "add"))
    assert actions.index(("EXPAND", "add")) < actions.index(
        ("RESULT_READY", None)
    )
    final_hide = actions.index(("HIDE", None), first_hide + 1)
    final_close = actions.index(("CLOSE", None), first_close + 1)
    assert actions.index(("RESULT_READY", None)) < final_hide < final_close


def test_fast_result_returns_from_default_report_without_forcing_help():
    actions: list[tuple[str, str | None]] = []

    def observe(action: str, command_name: str | None) -> None:
        actions.append((action, command_name))

    with create_pipe_input() as pipe_input:
        result = run_command_wait(
            "COMPARE",
            "analyzing",
            total=1,
            work=lambda _progress: "immediate result",
            help_entries=_entries(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            interactive=True,
            interval=0.01,
            on_help_action=observe,
            return_view=build_report_loading_view(
                "COMPARE",
                sections=("What mem understood", "Differences"),
            ),
        )

    assert result == "immediate result"
    assert ("RESULT_READY", None) in actions
    assert ("OPEN", None) not in actions


def test_loading_report_is_shaped_but_contains_no_semantic_result():
    view = build_report_loading_view(
        "FORGET",
        sections=("What mem understood", "Review decisions", "To do"),
    )
    text = "".join(fragment[1] for fragment in view.text)

    assert view.title == "FORGET REPORT · BUILDING"
    assert "CONTENT PENDING · THIS IS NOT A RESULT" in text
    assert "WHAT MEM UNDERSTOOD" in text
    assert "REVIEW DECISIONS" in text
    assert "╶" in text and "╴" in text


def test_background_work_and_help_actions_share_one_study_sequence(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    profile = _study_profile()
    attempt_uid = str(uuid.uuid4())
    active = begin_study_action_recording(
        profile=profile,
        store_dir=store_dir,
        attempt_uid=attempt_uid,
        operation="forget",
        stdin_tty=True,
        stdout_tty=True,
    )
    assert active is not None
    help_opened = threading.Event()
    result_ready = threading.Event()
    worker_recorded = threading.Event()

    def observe(action: str, _command_name: str | None) -> None:
        if action == "OPEN":
            help_opened.set()
        elif action == "RESULT_READY":
            result_ready.set()

    def work(_progress):
        if not help_opened.wait(3):
            raise RuntimeError("Help was not opened from the report view.")
        record_study_action(
            "TUI_ACTION",
            surface="worker",
            action="EXECUTED",
        )
        worker_recorded.set()
        return 7

    try:
        with create_pipe_input() as pipe_input:
            def drive_terminal() -> None:
                # The frozen return view is a real read-only viewport. Its
                # navigation joins the same Study action sequence.
                pipe_input.send_text("\x1b[B")
                pipe_input.send_text("cch")
                if not worker_recorded.wait(3) or not result_ready.wait(3):
                    pipe_input.send_text("\x03")
                    return
                pipe_input.send_text("h")

            driver = threading.Thread(target=drive_terminal, daemon=True)
            driver.start()
            assert run_command_wait(
                "FORGET",
                "analyzing",
                total=1,
                work=work,
                help_entries=_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                interactive=True,
                interval=0.01,
                on_help_action=observe,
                return_view=CommandWaitView(
                    title="FORGET REPORT · BUILDING",
                    text="REPORT\nline one\nline two\nline three",
                ),
                context_view=CommandWaitView(
                    title="FORGET CONFIRMED INPUTS · READ-ONLY",
                    text="SOURCE\nline one\nline two\nline three",
                ),
            ) == 7
            driver.join(timeout=3)
    finally:
        finish_study_action_recording(active, status="COMPLETED")

    events = StudyActionLedger(
        profile,
        store_dir=store_dir,
    ).events_for_attempt(attempt_uid)
    tui_actions = [
        event.data["action"]
        for event in events
        if event.action == "TUI_ACTION"
    ]

    assert "HELP OPEN" in tui_actions
    assert "RETURN VIEW DOWN" in tui_actions
    assert "CONFIRMED INPUTS OPEN" in tui_actions
    assert "CONFIRMED INPUTS CLOSE" in tui_actions
    assert "EXECUTED" in tui_actions
    assert "HELP RESULT_READY" in tui_actions
    assert "HELP HIDE" in tui_actions
    assert "HELP CLOSE" in tui_actions
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
