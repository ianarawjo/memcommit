"""Content-free recent-target launchers for Trace and Rationale."""

from __future__ import annotations

from dataclasses import replace

import pytest

from memcommit.persistence.command_ledger.attempts import (
    CommandAttemptError,
    CommandAttemptLedger,
    annotate_memory_report_attempt,
    begin_command_attempt,
    finish_command_attempt,
)
from memcommit.adapters.console.coordination.memory_report_recents import (
    MemoryReportRecentError,
    MemoryReportRecentSelection,
    MemoryReportSelectAction,
    choose_memory_report_recent,
    memory_report_recents,
)
from memcommit.application.capabilities.reviewing.read_report import ReadReportTarget
from memcommit.persistence.store import MemoryStore


def _record_report(
    store: MemoryStore,
    *,
    operation: str,
    context_name: str,
    memory_uid: str,
    started_at: str,
    status: str = "COMPLETED",
) -> str:
    active = begin_command_attempt(
        store_dir=store.store_dir,
        operation=operation,
        stdin_tty=True,
        stdout_tty=True,
    )
    active.record = replace(active.record, started_at=started_at)
    active.ledger.replace(active.record)
    annotate_memory_report_attempt(
        operation=operation,
        context_name=context_name,
        memory_uid=memory_uid,
    )
    finish_command_attempt(active, status=status)
    return active.record.uid


def test_recents_are_latest_unique_completed_targets_and_content_free(isolated_store):
    store = MemoryStore()
    _record_report(
        store,
        operation="trace",
        context_name="notes",
        memory_uid="memory-one",
        started_at="2026-08-06T10:00:00+00:00",
    )
    latest_uid = _record_report(
        store,
        operation="trace",
        context_name="notes",
        memory_uid="memory-one",
        started_at="2026-08-06T12:00:00+00:00",
    )
    _record_report(
        store,
        operation="trace",
        context_name="notes",
        memory_uid="failed-memory",
        started_at="2026-08-06T13:00:00+00:00",
        status="FAILED",
    )
    _record_report(
        store,
        operation="rationale",
        context_name="notes",
        memory_uid="rationale-memory",
        started_at="2026-08-06T14:00:00+00:00",
    )

    recents = memory_report_recents(store, operation="trace")

    assert [(item.attempt_uid, item.memory_uid) for item in recents] == [
        (latest_uid, "memory-one")
    ]
    latest = CommandAttemptLedger(isolated_store).load(latest_uid)
    assert latest.details == {
        "memory_report": {
            "operation": "trace",
            "context_name": "notes",
            "memory_uid": "memory-one",
        },
        "read_report": ReadReportTarget(
            operation="trace",
            context_names=("notes",),
            target_names=("notes",),
            selection_mode="SINGLE",
            ranges=("DIRECT",),
            memory_uid="memory-one",
        ).to_metadata(),
    }


def test_empty_launcher_goes_directly_to_common_memory_picker(
    isolated_store, monkeypatch
):
    monkeypatch.setattr(
        "memcommit.adapters.console.terminal.components.read_report.launcher.run_operation_launcher",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("an empty recent catalog must be skipped")
        ),
    )

    selected = choose_memory_report_recent(MemoryStore(), operation="trace")

    assert isinstance(selected, MemoryReportSelectAction)


def test_launcher_revalidates_selected_recent(isolated_store, monkeypatch):
    store = MemoryStore()
    _record_report(
        store,
        operation="rationale",
        context_name="research/granted",
        memory_uid="memory-two",
        started_at="2026-08-06T12:00:00+00:00",
    )

    def choose(recents, **kwargs):
        return recents[0].target

    monkeypatch.setattr(
        "memcommit.adapters.console.coordination.memory_report_recents.choose_read_report_recent",
        choose,
    )

    selected = choose_memory_report_recent(store, operation="rationale")

    assert selected == MemoryReportRecentSelection(
        context_name="research/granted",
        memory_uid="memory-two",
        include_descendants=True,
    )


def test_launcher_rejects_recent_that_changes_after_selection(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    attempt_uid = _record_report(
        store,
        operation="trace",
        context_name="notes",
        memory_uid="memory-three",
        started_at="2026-08-06T12:00:00+00:00",
    )

    def choose(recents, **kwargs):
        ledger = CommandAttemptLedger(store.store_dir)
        attempt = ledger.load(attempt_uid)
        ledger.replace(
            replace(
                attempt,
                details={
                    "memory_report": {
                        "operation": "trace",
                        "context_name": "other",
                        "memory_uid": "memory-three",
                    }
                },
            )
        )
        return recents[0].target

    monkeypatch.setattr(
        "memcommit.adapters.console.coordination.memory_report_recents.choose_read_report_recent",
        choose,
    )

    with pytest.raises(MemoryReportRecentError, match="changed"):
        choose_memory_report_recent(store, operation="trace")


def test_report_annotation_must_match_active_operation(isolated_store):
    active = begin_command_attempt(
        store_dir=isolated_store,
        operation="trace",
        stdin_tty=True,
        stdout_tty=True,
    )

    with pytest.raises(CommandAttemptError, match="active operation"):
        annotate_memory_report_attempt(
            operation="rationale",
            context_name="notes",
            memory_uid="memory-four",
        )

    finish_command_attempt(active, status="INTERRUPTED", failure_kind="TestCleanup")


def test_trace_recents_include_the_log_memory_alias(isolated_store):
    active = begin_command_attempt(
        store_dir=isolated_store,
        operation="log",
        stdin_tty=True,
        stdout_tty=True,
    )
    annotate_memory_report_attempt(
        operation="trace",
        context_name="notes",
        memory_uid="memory-through-log",
    )
    finish_command_attempt(active, status="COMPLETED")

    recents = memory_report_recents(MemoryStore(), operation="trace")

    assert [(item.context_name, item.memory_uid) for item in recents] == [
        ("notes", "memory-through-log")
    ]
