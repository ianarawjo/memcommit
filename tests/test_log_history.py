"""Interactive and semantic extensions to ``mem log``."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.context import Memory
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

    def choose_location(names, **kwargs):
        observed["locations"] = names
        observed["location_title"] = kwargs["title"]
        observed["annotations"] = kwargs["annotations"]
        observed["operation_rows"] = kwargs["operation_loader"]("notes")
        return "notes"

    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history_location",
        choose_location,
    )

    def choose(
        entries,
        *,
        context_name,
        mode,
        initial_details_open,
        empty_message,
        **_kwargs,
    ):
        observed["entries"] = entries
        observed["context_name"] = context_name
        observed["mode"] = mode
        observed["initial_details_open"] = initial_details_open
        observed["empty_message"] = empty_message
        return None

    monkeypatch.setattr("memcommit.commands.diff_browser.choose_history", choose)

    result = invoke("log")

    assert result.exit_code == 0
    assert observed["context_name"] == "notes"
    assert observed["locations"] == ("notes",)
    assert observed["location_title"] == "LOG · SELECT A CONTEXT"
    assert observed["annotations"]["notes"] == (
        "1 direct · 0 descendant operations"
    )
    assert [row.label for row in observed["operation_rows"]] == ["add"]
    assert observed["operation_rows"][0].style == "report-neutral"
    assert observed["mode"] == "log"
    assert observed["initial_details_open"] is True
    assert observed["empty_message"] == "No checkpoints for this Context yet."
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


def test_log_memory_plain_is_the_canonical_trace_projection(isolated_store):
    invoke("init", "notes")
    invoke("add", "one")
    memory_uid = _memory_uid("notes")

    through_log = invoke("log", "--memory", memory_uid, "--plain")
    through_trace = invoke("trace", memory_uid, "--plain")

    assert through_log.exit_code == 0, through_log.output
    assert through_trace.exit_code == 0, through_trace.output
    assert through_log.output == through_trace.output


def test_log_memory_uses_the_shared_trace_history_explorer(
    isolated_store,
    monkeypatch,
):
    invoke("init", "notes")
    invoke("add", "one")
    memory_uid = _memory_uid("notes")
    observed: dict[str, str] = {}
    monkeypatch.setattr("memcommit.commands.log._interactive_terminal", lambda: True)
    monkeypatch.setattr(
        "memcommit.commands.log.open_trace_history",
        lambda report, *, context_name: observed.update(
            context_name=context_name,
            memory_uid=report.selected_uid,
        ),
    )

    result = invoke("log", "--memory", memory_uid)

    assert result.exit_code == 0, result.output
    assert observed == {"context_name": "notes", "memory_uid": memory_uid}


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

    monkeypatch.setattr(
        "memcommit.commands.diff_browser.choose_history_location",
        lambda *args, **kwargs: "notes",
    )

    def choose(
        entries,
        *,
        context_name,
        mode,
        initial_details_open,
        empty_message,
        **_kwargs,
    ):
        observed["entries"] = entries
        return None

    monkeypatch.setattr("memcommit.commands.diff_browser.choose_history", choose)

    result = invoke("log", "--manual")

    assert result.exit_code == 0
    assert len(observed["entries"]) == 2
    assert "Transition: +0 added · ~0 edited · -0 removed" in (
        observed["entries"][0].detail
    )
