"""Natural-language entry contracts for an unsaved Ground."""
from __future__ import annotations

from typer.testing import CliRunner

import memcommit.commands.ground as ground_command
from memcommit.cli import app
from memcommit.store import MemoryStore


runner = CliRunner()


def test_sentence_positional_prints_seeded_unsaved_frame_without_writing(
    isolated_store,
):
    request = (
        "지금 Task 1을 위키와 사용자용 Context로 분리하고 싶어"
    )

    result = runner.invoke(app, ["ground", request])

    assert result.exit_code == 0, result.output
    assert "MEM GROUND · NEW · NOT SAVED" in result.output
    assert "WORKING · FROM STARTING REQUEST" in result.output
    assert result.output.count("NOT SAVED") == 1
    assert request in result.output
    assert "CONTEXTS\n  (not bound; not inferred)" in result.output
    assert "starting request was not sent to a provider" in result.output
    assert not isolated_store.exists()


def test_explicit_request_disambiguates_valid_name_like_text(
    isolated_store,
):
    result = runner.invoke(app, ["ground", "--request", "task-1"])

    assert result.exit_code == 0, result.output
    assert "WORKING · FROM STARTING REQUEST" in result.output
    assert "task-1" in result.output
    assert not isolated_store.exists()


def test_valid_portable_positional_keeps_named_ground_behavior(
    isolated_store,
):
    result = runner.invoke(app, ["ground", "task-1"])

    assert result.exit_code == 0, result.output
    saved = MemoryStore(create=False).load_ground_session("task-1")
    assert saved is not None
    assert saved.contract_name == "task-1"


def test_sentence_entry_rejects_named_ground_options_without_writing(
    isolated_store,
):
    result = runner.invoke(
        app,
        [
            "ground",
            "분리하고 싶어",
            "--goal",
            "This option requires a portable name.",
        ],
    )

    assert result.exit_code == 1
    assert "starting request cannot be combined" in result.output
    assert not isolated_store.exists()


def test_seeded_snapshot_escapes_terminal_controls(
    isolated_store,
):
    result = runner.invoke(
        app,
        ["ground", "review \x1b[31mTask 1"],
    )

    assert result.exit_code == 0, result.output
    assert "\x1b" not in result.output
    assert "Task 1" in result.output
    assert not isolated_store.exists()


def test_tty_sentence_passes_exact_working_goal_to_blank_shell(
    isolated_store,
    monkeypatch,
):
    request = "Split Task 1 into wiki and user-facing Contexts."
    seen: list[str] = []
    monkeypatch.setattr(
        ground_command,
        "_interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        ground_command,
        "_run_new_ground_shell",
        lambda initial_request="": seen.append(initial_request),
    )

    result = runner.invoke(app, ["ground", request])

    assert result.exit_code == 0, result.output
    assert seen == [request]
    assert not isolated_store.exists()


def test_ground_help_explains_name_or_request_entry():
    result = runner.invoke(app, ["ground", "--help"])

    assert result.exit_code == 0, result.output
    assert "[GROUND_NAME]" in result.output
    assert "natural-language" in result.output
    assert "--request" in result.output
