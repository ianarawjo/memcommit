"""Context-wide Trace and Rationale contracts."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _invoke(*args: str):
    return runner.invoke(app, list(args))


def _direct_memories(store: MemoryStore, name: str) -> tuple[Memory, ...]:
    return tuple(
        item
        for item in store.load_direct(name).iter_items()
        if isinstance(item, Memory)
    )


def _evolving_context() -> tuple[MemoryStore, Memory]:
    assert _invoke("init", "notes").exit_code == 0
    assert _invoke("add", "First wording").exit_code == 0
    store = MemoryStore()
    memory = _direct_memories(store, "notes")[0]
    assert _invoke("edit", memory.uid, "Second wording").exit_code == 0
    return store, memory


def test_trace_positional_context_returns_its_complete_lineage(isolated_store):
    _store, memory = _evolving_context()

    result = _invoke("trace", "notes")

    assert result.exit_code == 0, result.output + result.stderr
    assert "TRACE · notes" in result.output
    assert "[CONTEXT]" in result.output
    assert "LATEST FIRST" in result.output
    assert "First wording" in result.output
    assert "Second wording" in result.output
    assert f"[MEMORY {memory.uid[:8]}]" in result.output


def test_trace_context_json_names_the_context_subject(isolated_store):
    _evolving_context()

    result = _invoke("trace", "notes", "--json")

    assert result.exit_code == 0, result.output + result.stderr
    payload = json.loads(result.output)
    assert payload["target"] == "CONTEXT"
    assert payload["context"]["name"] == "notes"
    assert len(payload["events"]) >= 3


def test_trace_context_rejects_retired_tui_mode(isolated_store):
    _evolving_context()

    result = _invoke("trace", "notes", "--tui")

    assert result.exit_code == 2
    assert "No such option: --tui" in result.stderr


class _ContextRationaleProvider:
    calls: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "context rationale"
        assert output_schema is not None
        payload = json.loads(prompt.split("CONTEXT RATIONALE PAYLOAD:\n", 1)[1])
        self.calls.append(payload)
        return json.dumps(
            {
                "provenance": (
                    "The Context began with the first wording, and its recorded "
                    "Edit replaced that wording with the second."
                )
            }
        )


def test_rationale_context_uses_the_whole_context_trace(
    isolated_store,
    monkeypatch,
):
    _ContextRationaleProvider.calls.clear()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.history_recovery.inspection.rationale.command.connect_semantic_provider",
        _ContextRationaleProvider,
    )
    _evolving_context()

    result = _invoke("rationale", "notes")

    assert result.exit_code == 0, result.output + result.stderr
    assert "Rationale · notes" in result.output
    assert "CONTEXT" in result.output
    assert "RATIONALE" in result.output
    assert "recorded Edit replaced" in result.output
    request = _ContextRationaleProvider.calls[0]["request"]
    assert isinstance(request, dict)
    assert request["context_name"] == "notes"
    assert len(request["events"]) >= 3


def test_history_target_failure_uses_the_shared_context_suggestion(
    isolated_store,
):
    assert _invoke("init", "practice/rules").exit_code == 0

    result = _invoke("trace", "pracitce/rules")

    assert result.exit_code == 1
    assert "Context 'pracitce/rules' does not exist." in result.stderr
    assert "Did you mean 'practice/rules'?" in result.stderr
