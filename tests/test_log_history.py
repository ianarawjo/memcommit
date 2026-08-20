"""Stable printed and semantic output contracts for ``mem log``."""

from __future__ import annotations

import inspect
import json

import click
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands import log as log_command
from memcommit.context import Memory
from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def _memory_uid(context_name: str) -> str:
    return next(
        item.uid
        for item in MemoryStore().load_direct(context_name).iter_items()
        if isinstance(item, Memory)
    )


class CheckpointPlanProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split("HISTORY SEARCH PAYLOAD:\n", 1)[1])
        assert operation == "history search"
        assert payload["allowed_result_kinds"] == ["checkpoint"]
        return json.dumps(
            {
                "understanding": "Find the latest checkpoint.",
                "result_kind": "checkpoint",
                "subject_mode": "ALL",
                "subject_ids": [],
                "event_kinds": [],
                "anchor_kind": "NONE",
                "anchor_ids": [],
                "anchor_occurrence": "ANY",
                "relation": "NONE",
                "reduce": "LATEST",
            }
        )


def test_log_is_terminal_independent_and_prints_only_the_current_context(
    isolated_store,
):
    invoke("init", "other")
    invoke("add", "other memory")
    invoke("checkpoint", "other checkpoint")
    invoke("init", "notes")
    invoke("add", "note memory")
    invoke("checkpoint", "notes checkpoint")

    result = invoke("log")
    explicit = invoke("log", "--context", "other")

    assert result.exit_code == 0
    assert "Log for 'notes'" in result.output
    assert "notes checkpoint" in result.output
    assert "other checkpoint" not in result.output
    assert explicit.exit_code == 0
    assert "Log for 'other'" in explicit.output
    assert "other checkpoint" in explicit.output
    assert "notes checkpoint" not in explicit.output
    source = inspect.getsource(log_command)
    assert "_interactive_terminal" not in source
    assert "browse_checkpoint_locations" not in source
    assert "choose_history" not in source
    assert "history_display_row_segments" in source


def test_plain_remains_a_compatible_alias_for_the_static_report(isolated_store):
    invoke("init", "notes")
    invoke("add", "one")

    default = invoke("log")
    plain = invoke("log", "--plain")

    assert default.exit_code == 0
    assert plain.exit_code == 0
    assert default.output == plain.output


def test_log_colors_only_known_action_columns_in_a_color_terminal(isolated_store):
    invoke("init", "notes")
    added = invoke("add", "one")
    memory_uid = added.output.split("[", 1)[1].split("]", 1)[0]
    invoke("edit", memory_uid, "edited")
    invoke("remove", memory_uid)
    invoke("undo")
    invoke("redo")
    invoke("checkpoint", "reviewed baseline")

    colored = runner.invoke(app, ["log"], color=True)

    assert colored.exit_code == 0, colored.output
    expected = {
        "init": SemanticColorRole.CREATE,
        "add": SemanticColorRole.ADD,
        "edit": SemanticColorRole.EDIT,
        "remove": SemanticColorRole.REMOVE,
        "undo": SemanticColorRole.UNDO,
        "redo": SemanticColorRole.REDO,
        "checkpoint": SemanticColorRole.HISTORY,
    }
    for label, role in expected.items():
        assert click.style(
            f"[{label}]",
            fg=semantic_color_rgb(role),
            bold=True,
        ) in colored.output

    plain_output = click.unstyle(colored.output)
    assert "reviewed baseline" in plain_output
    assert "[CHECKPOINT " in plain_output
    assert "[RECEIPT " in plain_output
    assert "[SOURCE remove " in plain_output


def test_log_memory_always_prints_the_canonical_trace_projection(isolated_store):
    invoke("init", "notes")
    invoke("add", "one")
    memory_uid = _memory_uid("notes")

    through_log = invoke("log", "--memory", memory_uid)
    through_trace = invoke("trace", memory_uid, "--plain")

    assert through_log.exit_code == 0, through_log.output
    assert through_trace.exit_code == 0, through_trace.output
    assert through_log.output == through_trace.output


def test_semantic_log_prints_locally_resolved_checkpoint(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "one")
    monkeypatch.setattr(
        "memcommit.commands.log.connect_codex_chatgpt_provider",
        lambda: CheckpointPlanProvider(),
    )

    result = invoke("log", "latest checkpoint")

    assert result.exit_code == 0
    assert "History matches for 'notes'" in result.output
    assert "checkpoint" in result.output
    assert "add" in result.output
    assert "active checkpoint · restorable" in result.output


def test_manual_filter_applies_before_latest_semantic_reduction(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("checkpoint", "reviewed baseline")
    invoke("add", "newer automatic state")
    monkeypatch.setattr(
        "memcommit.commands.log.connect_codex_chatgpt_provider",
        lambda: CheckpointPlanProvider(),
    )

    result = invoke("log", "latest checkpoint", "--manual")

    assert result.exit_code == 0
    assert "reviewed baseline" in result.output
    assert "add" not in result.output


def test_manual_log_prints_only_manual_checkpoints(isolated_store):
    invoke("init", "notes")
    invoke("add", "one")
    invoke("checkpoint", "manual one")
    invoke("add", "two")
    invoke("checkpoint", "manual two")
    result = invoke("log", "--manual")

    assert result.exit_code == 0
    assert "manual one" in result.output
    assert "manual two" in result.output
    assert "add" not in result.output


def test_log_labels_uid_namespaces_and_separates_inherited_branch_history(
    isolated_store,
):
    invoke("init", "practice/1")
    added = invoke("add", "inherited memory")
    memory_uid = added.output.split("[", 1)[1].split("]", 1)[0]
    invoke("branch", "practice/2")
    invoke("remove", memory_uid)

    result = invoke("log")

    assert result.exit_code == 0, result.output
    assert "DIRECT COMMANDS · practice/2" in result.output
    assert "INHERITED HISTORY · source practice/1" in result.output
    assert "[CHECKPOINT " in result.output
    assert f"[MEMORY {memory_uid[:8]}]" in result.output
    assert "[init]" in result.output
    assert "not counted as a command" in result.output
