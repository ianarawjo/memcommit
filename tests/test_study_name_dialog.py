"""Interactive Study Profile name editor contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.commands.system_study_tools.init_study.name_dialog import choose_study_profile_name
from memcommit.application.operations.system_study_tools.init_study.application import generate_study_profile_name


def test_default_name_cursor_starts_at_end_for_immediate_editing() -> None:
    default = "study-20260806T143052Z-a1b2c3d4"
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("-pilot\r")
        selected = choose_study_profile_name(
            default,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == default + "-pilot"


def test_prefilled_name_can_be_replaced_and_escape_cancels() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x15pilot-001\r")
        selected = choose_study_profile_name(
            "study-20260806T143052Z-a1b2c3d4",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert selected == "pilot-001"

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        cancelled = choose_study_profile_name(
            "study-20260806T143052Z-a1b2c3d4",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert cancelled is None


def test_generated_default_uses_utc_and_uuid_prefix() -> None:
    assert generate_study_profile_name(
        created=datetime(2026, 8, 6, 14, 30, 52, tzinfo=timezone.utc),
        generated_uid=uuid.UUID("a1b2c3d4-0000-4000-8000-000000000000"),
    ) == "study-20260806T143052Z-a1b2c3d4"
