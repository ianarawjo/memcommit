"""Natural-language entry contracts for an unsaved Ground."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

import memcommit.commands.ground as ground_command
from memcommit import ops
from memcommit.cli import app
from memcommit.commands.ground_shell import GroundShellResult
from memcommit.ground_dialogue import (
    GroundDialogueError,
    GroundDialogueNewContextSuggestion,
    GroundDialogueProposal,
)
from memcommit.ground_workspace_runtime import load_ground_workspace
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
    assert "MEM GROUND · WORKING · NOT SAVED" in result.output
    assert "WORKING · FROM STARTING REQUEST" not in result.output
    assert result.output.count("NOT SAVED") == 1
    assert request in result.output
    assert "CHAT\n  YOU · STARTING REQUEST" in result.output
    assert "DIALOGUE" not in result.output
    assert "CONTEXTS\n  (not bound; not inferred)" in result.output
    assert "submitted request starts the agent's Context discovery turn" in (
        result.output
    )
    assert "may show one NEW? Context" in result.output
    assert "unsaved Rule and Memory drafts" in result.output
    assert not isolated_store.exists()


def test_explicit_request_disambiguates_valid_name_like_text(
    isolated_store,
):
    result = runner.invoke(app, ["ground", "--request", "task-1"])

    assert result.exit_code == 0, result.output
    assert "MEM GROUND · WORKING · NOT SAVED" in result.output
    assert "WORKING · FROM STARTING REQUEST" not in result.output
    assert "task-1" in result.output
    assert not isolated_store.exists()


def test_valid_portable_positional_keeps_named_ground_behavior(
    isolated_store,
):
    result = runner.invoke(app, ["ground", "task-1"])

    assert result.exit_code == 0, result.output
    saved = load_ground_workspace(MemoryStore(create=False), "task-1")
    assert saved.name == "task-1"
    assert saved.manifest.revision == 0
    assert not (isolated_store / "ground-sessions").exists()


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


def test_new_ground_shell_discovers_context_names_before_agent_turn(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    store.save(ops.init("campus-wiki"))
    store.save(ops.init("temp/task-1"))
    store.set_current("temp/task-1")
    seen: list[tuple[str, tuple[str, ...]]] = []

    monkeypatch.setattr(
        ground_command,
        "_interpret_new_ground_turn",
        lambda text, *, context_names=None: seen.append(
            (text, tuple(context_names or ()))
        ),
    )

    def fake_shell(**kwargs):
        assert kwargs["context_catalog_count"] == 2
        assert kwargs["current_context_name"] == "temp/task-1"
        kwargs["interpret"]("Split Task 1 into wiki material.")
        return GroundShellResult(status="CANCELLED")

    monkeypatch.setattr(
        ground_command,
        "run_ground_shell",
        fake_shell,
    )

    ground_command._run_new_ground_shell(
        "Split Task 1 into wiki material."
    )

    assert seen == [
        (
            "Split Task 1 into wiki material.",
            ("campus-wiki", "temp/task-1"),
        )
    ]


def test_new_ground_shell_without_store_has_no_current_snapshot(
    isolated_store,
    monkeypatch,
):
    seen = []

    def fake_shell(**kwargs):
        seen.append(kwargs)
        return GroundShellResult(status="CANCELLED")

    monkeypatch.setattr(
        ground_command,
        "run_ground_shell",
        fake_shell,
    )

    ground_command._run_new_ground_shell("Start from a blank store.")

    assert len(seen) == 1
    assert seen[0]["current_context_name"] is None
    assert "context_catalog_count" not in seen[0]
    assert not isolated_store.exists()


def test_new_context_suggestion_is_checked_without_creating_or_switching(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    store.save(ops.init("ticker-rule-examples"))
    store.set_current("ticker-rule-examples")
    before_current = store.current_context_name()
    turn = GroundDialogueProposal(
        understanding="A dedicated ticker example Context may help.",
        question="Create this Ground?",
        ground_name="ticker-rules",
        goal="Find reusable company-name to ticker Rules.",
        new_context_suggestions=(
            GroundDialogueNewContextSuggestion(
                context_name="ticker-rule-examples",
                reason="A dedicated example set may help.",
            ),
        ),
    )
    monkeypatch.setattr(
        ground_command,
        "interpret_ground_dialogue",
        lambda *_args, **_kwargs: turn,
    )

    with pytest.raises(
        GroundDialogueError,
        match="not currently creatable",
    ):
        ground_command._interpret_new_ground_turn(
            "Find a reusable ticker Rule.",
            context_names=(),
        )

    assert store.list_context_names() == ["ticker-rule-examples"]
    assert store.current_context_name() == before_current


def test_ground_help_explains_name_or_request_entry():
    result = runner.invoke(app, ["ground", "--help"])

    assert result.exit_code == 0, result.output
    assert "[GROUND_NAME]" in result.output
    assert "natural-language" in result.output
    assert "--request" in result.output
    assert "provider-backed chat" in result.output
