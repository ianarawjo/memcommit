"""Profile-scoped command-attempt audit contracts."""
from __future__ import annotations

import json

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.command_attempts import (
    CommandAttempt,
    CommandAttemptLedger,
    annotate_command_outcome,
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


def test_command_text_and_outcome_are_durable_and_older_versions_remain_readable(
    isolated_store,
):
    active = begin_command_attempt(
        store_dir=isolated_store,
        operation="chunk",
        stdin_tty=False,
        stdout_tty=False,
        command_argv=("chunk", "two words"),
    )
    annotate_command_outcome("NO_CHANGE")

    running = CommandAttemptLedger(isolated_store).load(active.record.uid)
    assert running.status == "RUNNING"
    assert running.outcome == "NO_CHANGE"

    finished = finish_command_attempt(active, status="COMPLETED")
    assert finished.outcome == "NO_CHANGE"
    assert finished.command == "mem chunk 'two words'"
    encoded = finished.to_dict()
    assert encoded["version"] == 3

    version_two = dict(encoded)
    version_two["version"] = 2
    version_two.pop("command")
    restored_two = CommandAttempt.from_dict(version_two)
    assert restored_two.status == "COMPLETED"
    assert restored_two.outcome == "NO_CHANGE"
    assert restored_two.command is None

    version_one = dict(version_two)
    version_one["version"] = 1
    version_one.pop("outcome")
    restored_one = CommandAttempt.from_dict(version_one)
    assert restored_one.status == "COMPLETED"
    assert restored_one.outcome is None
    assert restored_one.command is None


def test_failure_supersedes_a_provisional_completion_outcome(isolated_store):
    active = begin_command_attempt(
        store_dir=isolated_store,
        operation="edit",
        stdin_tty=False,
        stdout_tty=False,
    )
    annotate_command_outcome("NO_CHANGE")

    finished = finish_command_attempt(
        active,
        status="FAILED",
        failure_kind="RenderError",
        exit_code=1,
    )

    assert finished.status == "FAILED"
    assert finished.outcome is None


def test_root_logs_success_failure_and_complete_command_argv(
    isolated_store,
    monkeypatch,
):
    _enable_attempt_log(monkeypatch)

    created = runner.invoke(app, ["init", "private-context-name"])
    failed = runner.invoke(app, ["add", "private Memory body"])

    assert created.exit_code == 0
    assert failed.exit_code == 0
    records = CommandAttemptLedger(isolated_store).list()
    assert [record.operation for record in records[:2]] == ["add", "init"]
    assert {record.status for record in records[:2]} == {"COMPLETED"}
    encoded = json.dumps([record.to_dict() for record in records], ensure_ascii=False)
    assert records[0].command == "mem add 'private Memory body'"
    assert records[1].command == "mem init private-context-name"
    assert "private Memory body" in encoded
    assert "private-context-name" in encoded

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
            "-r",
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
    added = runner.invoke(app, ["add", "unchanged content"])
    assert added.exit_code == 0
    memory_uid = added.output.split("[", 1)[1].split("]", 1)[0]
    unchanged = runner.invoke(app, ["edit", memory_uid, "unchanged content"])
    assert unchanged.exit_code == 0

    shown = runner.invoke(app, ["log", "--operations"])

    assert shown.exit_code == 0, shown.output
    assert "Operation attempts · recent first" in shown.output
    assert "COMPLETED" not in shown.output
    assert "NO CHANGE" in shown.output
    assert "init" in shown.output
    assert "command=mem init working" in shown.output
    assert "command=mem add 'unchanged content'" in shown.output
    assert "log" not in shown.output.split("Operation attempts", 1)[1]
    records = CommandAttemptLedger(isolated_store).list()
    assert [record.operation for record in records[:4]] == [
        "log",
        "edit",
        "add",
        "init",
    ]
    assert records[1].outcome == "NO_CHANGE"


def test_cancelled_edit_is_qualified_without_a_completed_label(
    isolated_store,
    monkeypatch,
):
    import memcommit.commands.edit as edit_command

    _enable_attempt_log(monkeypatch)
    assert runner.invoke(app, ["init", "working"]).exit_code == 0
    monkeypatch.setattr(edit_command, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        edit_command,
        "choose_edit_setup",
        lambda *_args, **_kwargs: None,
    )

    cancelled = runner.invoke(app, ["edit"])
    shown = runner.invoke(app, ["log", "--operations"])

    assert cancelled.exit_code == 0
    attempt = CommandAttemptLedger(isolated_store).list()[1]
    assert attempt.operation == "edit"
    assert attempt.status == "COMPLETED"
    assert attempt.outcome == "CANCELLED"
    assert "CANCELLED" in shown.output
    assert "COMPLETED" not in shown.output


def test_chunk_without_splittable_memory_records_no_change_not_a_checkpoint(
    isolated_store,
    monkeypatch,
):
    _enable_attempt_log(monkeypatch)
    assert runner.invoke(app, ["init", "working"]).exit_code == 0
    assert runner.invoke(app, ["add", "one clause"]).exit_code == 0
    store = MemoryStore()
    checkpoint_count = len(store.list_checkpoints("working"))

    result = runner.invoke(app, ["chunk"])

    assert result.exit_code == 0, result.output
    attempt = CommandAttemptLedger(isolated_store).list()[0]
    assert attempt.operation == "chunk"
    assert attempt.status == "COMPLETED"
    assert attempt.outcome == "NO_CHANGE"
    assert len(store.list_checkpoints("working")) == checkpoint_count


def test_operation_log_calls_unfinalized_start_not_finalized(
    isolated_store,
    monkeypatch,
):
    _enable_attempt_log(monkeypatch)
    active = begin_command_attempt(
        store_dir=isolated_store,
        operation="chunk",
        stdin_tty=False,
        stdout_tty=False,
    )
    try:
        shown = runner.invoke(app, ["log", "--operations"])
    finally:
        finish_command_attempt(
            active,
            status="INTERRUPTED",
            failure_kind="TestCleanup",
        )

    assert shown.exit_code == 0, shown.output
    assert "NOT FINALIZED" in shown.output
    assert "RUNNING" not in shown.output
