"""Terminal-host routing for the one frozen Trace report."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.trace import (
    command as trace_command,
)
from memcommit.application.operations.trace.application import (
    ContextHistorySlice,
    MemoryHistory,
)
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def _memory_uid(context_name: str) -> str:
    return next(
        item.uid
        for item in MemoryStore().load_direct(context_name).iter_items()
        if isinstance(item, Memory)
    )


def test_interactive_context_trace_opens_the_existing_read_only_viewer(
    isolated_store,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "viewer-context"]).exit_code == 0
    assert runner.invoke(app, ["add", "first Memory"]).exit_code == 0
    viewed: dict[str, object] = {}
    monkeypatch.setattr(trace_command, "interactive_report_terminal", lambda: True)
    monkeypatch.setattr(
        trace_command,
        "open_context_trace_viewer",
        lambda report, **kwargs: viewed.update(report=report, kwargs=kwargs),
    )

    result = runner.invoke(app, ["trace", "viewer-context", "--limit", "7"])

    assert result.exit_code == 0, result.output
    assert isinstance(viewed["report"], ContextHistorySlice)
    assert viewed["kwargs"] == {"verbose": False, "limit": 7}
    assert "TRACE ·" not in result.output


def test_interactive_direct_memory_trace_opens_the_existing_read_only_viewer(
    isolated_store,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "viewer-memory"]).exit_code == 0
    assert runner.invoke(app, ["add", "first wording"]).exit_code == 0
    uid = _memory_uid("viewer-memory")
    assert runner.invoke(app, ["edit", uid, "second wording"]).exit_code == 0
    viewed: dict[str, object] = {}
    monkeypatch.setattr(trace_command, "interactive_report_terminal", lambda: True)
    monkeypatch.setattr(
        trace_command,
        "open_trace_viewer",
        lambda report, **kwargs: viewed.update(report=report, kwargs=kwargs),
    )

    result = runner.invoke(app, ["trace", uid, "--all", "--verbose"])

    assert result.exit_code == 0, result.output
    assert isinstance(viewed["report"], MemoryHistory)
    assert viewed["kwargs"] == {"verbose": True, "limit": None}
    assert "TRACE ·" not in result.output


def test_noninteractive_trace_keeps_the_static_document(
    isolated_store,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "static-memory"]).exit_code == 0
    assert runner.invoke(app, ["add", "portable wording"]).exit_code == 0
    uid = _memory_uid("static-memory")
    monkeypatch.setattr(trace_command, "interactive_report_terminal", lambda: False)
    monkeypatch.setattr(
        trace_command,
        "open_trace_viewer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a noninteractive Trace must not open the Viewer")
        ),
    )

    result = runner.invoke(app, ["trace", uid])

    assert result.exit_code == 0, result.output
    assert "TRACE · static-memory" in result.output
    assert "portable wording" in result.output


def test_json_bypasses_the_viewer_even_when_the_terminal_is_interactive(
    isolated_store,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "json-memory"]).exit_code == 0
    assert runner.invoke(app, ["add", "machine-readable wording"]).exit_code == 0
    uid = _memory_uid("json-memory")
    monkeypatch.setattr(trace_command, "interactive_report_terminal", lambda: True)
    monkeypatch.setattr(
        trace_command,
        "open_trace_viewer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("JSON must not open the Viewer")
        ),
    )

    result = runner.invoke(app, ["trace", uid, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["context"]["name"] == "json-memory"
    assert payload["selected_uid"] == uid
