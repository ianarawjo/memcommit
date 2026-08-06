"""Profile-scoped command-attempt audit contracts."""
from __future__ import annotations

import json

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.command_attempts import (
    CommandAttemptLedger,
    begin_command_attempt,
    finish_command_attempt,
)
from memcommit.commands import sever as sever_command
from memcommit.query_provider import QueryProviderTimeoutError
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _enable_attempt_log(monkeypatch):
    monkeypatch.delenv("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG", raising=False)


def _context(store: MemoryStore, name: str, *contents: str):
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.create_context(context)
    return context


def test_started_attempt_is_durable_before_command_completion(isolated_store):
    active = begin_command_attempt(
        store_dir=isolated_store,
        operation="sever",
        stdin_tty=True,
        stdout_tty=True,
    )

    retained = CommandAttemptLedger(isolated_store).load(active.record.uid)

    assert retained.status == "RUNNING"
    assert retained.completed_at is None
    assert retained.elapsed_seconds is None
    finish_command_attempt(active, status="INTERRUPTED", failure_kind="TestCleanup")


def test_root_logs_success_failure_and_never_raw_argv(isolated_store, monkeypatch):
    _enable_attempt_log(monkeypatch)

    created = runner.invoke(app, ["init", "private-context-name"])
    failed = runner.invoke(app, ["add", "private Memory body"])

    assert created.exit_code == 0
    assert failed.exit_code == 0
    records = CommandAttemptLedger(isolated_store).list()
    assert [record.operation for record in records[:2]] == ["add", "init"]
    assert {record.status for record in records[:2]} == {"COMPLETED"}
    encoded = json.dumps([record.to_dict() for record in records], ensure_ascii=False)
    assert "private Memory body" not in encoded
    assert "private-context-name" not in encoded

    invalid = runner.invoke(app, ["show", "missing-selector"])
    assert invalid.exit_code == 1
    latest = CommandAttemptLedger(isolated_store).list()[0]
    assert latest.operation == "show"
    assert latest.status == "FAILED"
    assert latest.failure is not None
    assert latest.failure["exit_code"] == 1


def test_failed_sever_attempt_retains_bounded_frame_diagnostics(
    isolated_store,
    monkeypatch,
):
    _enable_attempt_log(monkeypatch)
    store = MemoryStore()
    _context(store, "local/source", "One", "Two")
    _context(store, "local/criteria", "Criterion")

    class TimedOutProvider:
        timeout = 600

        class identity:
            provider = "codex_chatgpt"

        def complete(self, *args, **kwargs):
            raise QueryProviderTimeoutError(
                "The temporary Codex sever_context timed out after 600 seconds."
            )

    monkeypatch.setattr(
        sever_command,
        "connect_codex_chatgpt_provider",
        TimedOutProvider,
    )

    result = runner.invoke(
        app,
        [
            "sever",
            "--source",
            "local/source",
            "--criteria",
            "local/criteria",
            "--save-as",
            "local/result",
        ],
    )

    assert result.exit_code == 1
    attempt = CommandAttemptLedger(isolated_store).list()[0]
    assert attempt.operation == "sever"
    assert attempt.status == "FAILED"
    assert attempt.details == {
        "sever": {
            "source_name": "local/source",
            "source_scope": "INCLUDE_DESCENDANTS",
            "source_memory_count": 2,
            "criteria_name": "local/criteria",
            "criteria_scope": "INCLUDE_DESCENDANTS",
            "criteria_memory_count": 1,
            "output_name": "local/result",
            "excluded_query_context_count": 0,
            "provider": "codex_chatgpt",
            "provider_timeout_seconds": 600,
            "failure_kind": "TIMEOUT",
        }
    }


def test_operation_log_lists_prior_attempt_without_listing_itself(
    isolated_store,
    monkeypatch,
):
    _enable_attempt_log(monkeypatch)
    assert runner.invoke(app, ["init", "working"]).exit_code == 0

    shown = runner.invoke(app, ["log", "--operations"])

    assert shown.exit_code == 0, shown.output
    assert "Operation attempts · recent first" in shown.output
    assert "COMPLETED" in shown.output
    assert "init" in shown.output
    assert "log" not in shown.output.split("Operation attempts", 1)[1]
    records = CommandAttemptLedger(isolated_store).list()
    assert [record.operation for record in records[:2]] == ["log", "init"]
