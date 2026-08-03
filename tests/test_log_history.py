"""Interactive and semantic extensions to ``mem log``."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.cli import app


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


class CheckpointPlanProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(
            prompt.split("HISTORY SEARCH PAYLOAD:\n", 1)[1]
        )
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


def test_tty_log_opens_shared_picker(isolated_store, monkeypatch):
    invoke("init", "notes")
    invoke("add", "one")
    observed = {}

    monkeypatch.setattr(
        "memcommit.commands.log._interactive_terminal",
        lambda: True,
    )

    def choose(entries, *, context_name, mode):
        observed["entries"] = entries
        observed["context_name"] = context_name
        observed["mode"] = mode
        return None

    monkeypatch.setattr("memcommit.commands.log.choose_history", choose)

    result = invoke("log")

    assert result.exit_code == 0
    assert observed["context_name"] == "notes"
    assert observed["mode"] == "log"
    assert len(observed["entries"]) == 2
    assert "Snapshot:" in observed["entries"][0].detail


def test_plain_log_bypasses_picker_even_in_a_tty(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    monkeypatch.setattr(
        "memcommit.commands.log._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.log.choose_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("plain log must not open the picker")
        ),
    )

    result = invoke("log", "--plain")

    assert result.exit_code == 0
    assert "Log for 'notes'" in result.output


def test_semantic_log_prints_locally_resolved_checkpoint_outside_tty(
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


def test_manual_picker_detail_uses_the_actual_preceding_checkpoint(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "one")
    invoke("checkpoint", "manual one")
    invoke("add", "two")
    invoke("checkpoint", "manual two")
    observed = {}
    monkeypatch.setattr(
        "memcommit.commands.log._interactive_terminal",
        lambda: True,
    )

    def choose(entries, *, context_name, mode):
        observed["entries"] = entries
        return None

    monkeypatch.setattr("memcommit.commands.log.choose_history", choose)

    result = invoke("log", "--manual")

    assert result.exit_code == 0
    assert len(observed["entries"]) == 2
    assert "Transition: +0 added · ~0 edited · -0 removed" in (
        observed["entries"][0].detail
    )
