"""Reviewed input and close-after-deletion contracts across picker components."""

from __future__ import annotations

import threading

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.commands.profile.picker.app import choose_profile
from memcommit.adapters.console.commands.profile.picker.model import (
    ProfilePickerEntry,
    ProfilePickerRefresh,
)
from memcommit.adapters.console.terminal.components.background_turn import (
    BackgroundExecutorTurn,
)

ENTRIES = (
    ProfilePickerEntry("authoring", 1, "notes", uid="authoring-uid"),
    ProfilePickerEntry("work", 2, "work/notes", uid="work-uid"),
)


@pytest.mark.parametrize(
    "key, kind", [("n", "CREATE_PROFILE"), ("r", "RENAME_PROFILE")]
)
def test_review_back_reopens_editable_draft_and_backspace_still_deletes(key, kind):
    with create_pipe_input() as pipe:
        # Return from review, edit the preserved draft, and approve the new name.
        pipe.send_text(key + "\x15draftx\r\x1b\x7f\ra")
        action = choose_profile(
            ENTRIES,
            current="authoring",
            registry_generation=9,
            app_input=pipe,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert action.kind == kind
    assert action.registry_generation == 9
    if kind == "CREATE_PROFILE":
        assert action.name == "draft"
        assert action.uid is None
    else:
        assert action.name == "authoring"
        assert action.new_name == "draft"
        assert action.uid == "authoring-uid"


@pytest.mark.parametrize("close_key", ["\x1b", "\x03"])
@pytest.mark.parametrize("fail", [False, True])
def test_busy_deletion_defers_close_and_preserves_success_or_error_receipt(
    monkeypatch,
    close_key,
    fail,
):
    started = threading.Event()
    close_observed = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    calls = []
    feeder_errors = []
    failure = RuntimeError("Deletion callback failed")
    original_request_close = BackgroundExecutorTurn.request_close

    def request_close(turn):
        requested = original_request_close(turn)
        if requested:
            close_observed.set()
        return requested

    monkeypatch.setattr(BackgroundExecutorTurn, "request_close", request_close)

    def remove(action):
        calls.append(action)
        started.set()
        if not release.wait(3):
            raise AssertionError("test did not release deletion")
        finished.set()
        if fail:
            raise failure
        return "Deletion completed"

    with create_pipe_input() as pipe:

        def feed():
            try:
                pipe.send_text("\x1b[Bd\r")
                assert started.wait(3), "deletion did not start"
                # Extra approval keys must not start a second destructive turn.
                pipe.send_text("a\r" + close_key)
                assert close_observed.wait(3), "close was not deferred"
                assert not finished.is_set()
            except BaseException as error:
                feeder_errors.append(error)
                pipe.send_text("\x03")
            finally:
                release.set()

        feeder = threading.Thread(target=feed)
        feeder.start()
        result = choose_profile(
            ENTRIES,
            current="authoring",
            registry_generation=9,
            apply_removal=remove,
            app_input=pipe,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=3)

    assert not feeder.is_alive()
    assert feeder_errors == []
    assert finished.is_set()
    assert len(calls) == 1
    assert calls[0].name == "work"
    assert calls[0].uid == "work-uid"
    assert calls[0].registry_generation == 9
    assert result == ProfilePickerRefresh(
        status="" if fail else "Deletion completed",
        error=failure if fail else None,
        close_requested=True,
        preferred_row_index=1,
    )
