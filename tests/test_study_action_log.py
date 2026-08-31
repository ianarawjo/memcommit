"""Detailed action contracts for current Study Profiles."""

from __future__ import annotations

import json
import shlex
import uuid

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.keys import Keys
import pytest

from memcommit.application.operations.profiles.profile.config import (
    ProfileEntry,
    study_run_identity,
)
from memcommit.persistence.command_ledger.study_actions import (
    StudyActionError,
    StudyActionLedger,
    StudyRecordingInput,
    begin_study_action_recording,
    finish_study_action_recording,
    record_study_help_lookup_completed,
    record_study_help_lookup_submitted,
    record_study_provider_turn,
)


def _study_profile(*, role: str = "PARTICIPANT") -> ProfileEntry:
    study_uid = "11111111-1111-4111-8111-111111111111"
    source_kind = "STUDY_RUN" if role == "PARTICIPANT" else "STUDY_RUN_GRANTED_MEMORY"
    return ProfileEntry(
        uid=(
            "22222222-2222-4222-8222-222222222222"
            if role == "PARTICIPANT"
            else "33333333-3333-4333-8333-333333333333"
        ),
        name="study-run" if role == "PARTICIPANT" else "study-run-granted-memory",
        kind="MANAGED",
        source={
            "kind": source_kind,
            "study_uid": study_uid,
            "study_name": "study-run",
            "created_at": "2026-08-09T20:34:05+00:00",
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": "44444444-4444-4444-8444-444444444444",
            "baseline_profile_name": "study-baseline",
        },
    )


def test_study_identity_comes_from_provenance_not_display_name():
    profile = _study_profile()
    renamed = ProfileEntry(
        uid=profile.uid,
        name="renamed-run",
        kind=profile.kind,
        source=profile.source,
    )

    identity = study_run_identity(renamed)

    assert identity is not None
    assert identity.name == "study-run"
    assert identity.role == "PARTICIPANT"


def test_study_input_log_keeps_navigation_but_redacts_printable_text(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    attempt_uid = str(uuid.uuid4())
    active = begin_study_action_recording(
        profile=_study_profile(),
        store_dir=store_dir,
        attempt_uid=attempt_uid,
        operation="query",
        stdin_tty=True,
        stdout_tty=True,
    )
    assert active is not None
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Bprivate answer\r")
        recorder = StudyRecordingInput(pipe_input)
        presses = recorder.read_keys()
        assert presses
    finish_study_action_recording(active, status="COMPLETED")

    events = StudyActionLedger(
        _study_profile(),
        store_dir=store_dir,
    ).events_for_attempt(attempt_uid)
    keys = [event.data["key"] for event in events if event.action == "KEY"]
    text_events = [event for event in events if event.action == "TEXT_INPUT"]
    encoded = json.dumps([event.to_dict() for event in events])

    assert "down" in keys
    assert any(event.data["character_count"] == 14 for event in text_events)
    assert "private answer" not in encoded
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))


def test_study_input_log_passes_through_cpr_and_normalizes_control_keys(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    attempt_uid = str(uuid.uuid4())
    active = begin_study_action_recording(
        profile=_study_profile(),
        store_dir=store_dir,
        attempt_uid=attempt_uid,
        operation="init",
        stdin_tty=True,
        stdout_tty=True,
    )
    assert active is not None
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[12;34R\x1c")
        recorder = StudyRecordingInput(pipe_input)
        presses = recorder.read_keys()
        assert any(press.key == Keys.CPRResponse for press in presses)
    finish_study_action_recording(active, status="COMPLETED")

    events = StudyActionLedger(
        _study_profile(),
        store_dir=store_dir,
    ).events_for_attempt(attempt_uid)
    keys = [event.data["key"] for event in events if event.action == "KEY"]

    assert keys == ["ControlBackslash"]
    assert all("cursor-position" not in str(key) for key in keys)
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))


def test_provider_turn_records_only_sizes_and_status(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    attempt_uid = str(uuid.uuid4())
    active = begin_study_action_recording(
        profile=_study_profile(),
        store_dir=store_dir,
        attempt_uid=attempt_uid,
        operation="find",
        stdin_tty=False,
        stdout_tty=False,
    )
    assert active is not None

    class Provider:
        class identity:
            provider = "test-provider"

        @record_study_provider_turn
        def complete(
            self,
            prompt: str,
            *,
            operation: str,
            output_schema: dict[str, object] | None = None,
        ) -> str:
            return "private result"

    assert (
        Provider().complete(
            "private prompt",
            operation="find",
            output_schema={"type": "object"},
        )
        == "private result"
    )
    finish_study_action_recording(active, status="COMPLETED")

    events = StudyActionLedger(
        _study_profile(),
        store_dir=store_dir,
    ).events_for_attempt(attempt_uid)
    encoded = json.dumps([event.to_dict() for event in events])
    started = next(event for event in events if event.action == "PROVIDER_TURN_STARTED")
    completed = next(
        event for event in events if event.action == "PROVIDER_TURN_COMPLETED"
    )

    assert started.data["input_characters"] == len("private prompt")
    assert started.data["has_schema"] is True
    assert completed.data["output_characters"] == len("private result")
    assert "private prompt" not in encoded
    assert "private result" not in encoded


def test_participant_log_retains_full_command_and_focused_help_lookup(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    attempt_uid = str(uuid.uuid4())
    command_argv = ("help", "why are these alike?")
    active = begin_study_action_recording(
        profile=_study_profile(),
        store_dir=store_dir,
        attempt_uid=attempt_uid,
        operation="help",
        stdin_tty=False,
        stdout_tty=False,
        command_argv=command_argv,
    )
    assert active is not None

    submitted = record_study_help_lookup_submitted("why are these alike?")
    completed = record_study_help_lookup_completed(("compare", "search", "query"))
    finish_study_action_recording(active, status="COMPLETED")

    events = StudyActionLedger(
        _study_profile(),
        store_dir=store_dir,
    ).events_for_attempt(attempt_uid)
    entered = next(event for event in events if event.action == "COMMAND_ENTERED")

    assert entered.data == {"command": shlex.join(("mem", *command_argv))}
    assert submitted is not None
    assert submitted.data == {"request": "why are these alike?"}
    assert completed is not None
    assert completed.data == {
        "rank_1": "compare",
        "rank_2": "search",
        "rank_3": "query",
    }


def test_granted_memory_log_does_not_retain_command_or_help_text(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    attempt_uid = str(uuid.uuid4())
    profile = _study_profile(role="GRANTED_MEMORY")
    active = begin_study_action_recording(
        profile=profile,
        store_dir=store_dir,
        attempt_uid=attempt_uid,
        operation="help",
        stdin_tty=False,
        stdout_tty=False,
        command_argv=("help", "private researcher wording"),
    )
    assert active is not None

    assert record_study_help_lookup_submitted("private researcher wording") is None
    assert record_study_help_lookup_completed(("query", "search", "help")) is None
    finish_study_action_recording(active, status="COMPLETED")

    events = StudyActionLedger(
        profile,
        store_dir=store_dir,
    ).events_for_attempt(attempt_uid)
    assert [event.action for event in events] == [
        "COMMAND_STARTED",
        "COMMAND_FINISHED",
    ]
    assert "private researcher wording" not in json.dumps(
        [event.to_dict() for event in events]
    )


def test_rejected_event_does_not_advance_the_durable_sequence(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    attempt_uid = str(uuid.uuid4())
    active = begin_study_action_recording(
        profile=_study_profile(),
        store_dir=store_dir,
        attempt_uid=attempt_uid,
        operation="meld",
        stdin_tty=True,
        stdout_tty=True,
    )
    assert active is not None

    with pytest.raises(StudyActionError, match="Study action key is invalid"):
        active.append("KEY", key="bad\nkey", count=1, focus="BufferControl")
    retained = active.append("KEY", key="down", count=1, focus="BufferControl")
    finish_study_action_recording(active, status="COMPLETED")

    assert retained.sequence == 2
    events = StudyActionLedger(
        _study_profile(),
        store_dir=store_dir,
    ).events_for_attempt(attempt_uid)
    assert [event.sequence for event in events] == [1, 2, 3]


def test_decision_free_auto_accept_is_an_allowlisted_content_free_action(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    attempt_uid = str(uuid.uuid4())
    active = begin_study_action_recording(
        profile=_study_profile(),
        store_dir=store_dir,
        attempt_uid=attempt_uid,
        operation="atomize",
        stdin_tty=True,
        stdout_tty=True,
    )
    assert active is not None

    automatic = active.append(
        "DECISION_FREE_AUTO_ACCEPT",
        surface="resolution",
        action="ACCEPT",
    )
    finish_study_action_recording(active, status="COMPLETED")

    events = StudyActionLedger(
        _study_profile(),
        store_dir=store_dir,
    ).events_for_attempt(attempt_uid)
    assert automatic.sequence == 2
    assert automatic.data == {"surface": "resolution", "action": "ACCEPT"}
    assert [event.action for event in events] == [
        "COMMAND_STARTED",
        "DECISION_FREE_AUTO_ACCEPT",
        "COMMAND_FINISHED",
    ]
