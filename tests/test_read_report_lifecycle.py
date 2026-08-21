"""Shared content-free lifecycle tests for Read Report operations."""

from __future__ import annotations

from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.command_attempts import (
    CommandAttemptError,
    CommandAttemptLedger,
    annotate_read_report_attempt,
    begin_command_attempt,
    finish_command_attempt,
)
from memcommit.interfaces.tui.workbenches.read_report import (
    ReadReportSelectTarget,
    choose_read_report_recent,
)
from memcommit.read_report import ReadReportError, ReadReportTarget
from memcommit.read_report_recents import (
    read_report_recents,
    revalidate_read_report_recent,
)
from memcommit.store import MemoryStore


def _record(store: MemoryStore, target: ReadReportTarget, started_at: str) -> str:
    active = begin_command_attempt(
        store_dir=store.store_dir,
        operation=target.operation,
        stdin_tty=True,
        stdout_tty=True,
    )
    active.record = replace(active.record, started_at=started_at)
    active.ledger.replace(active.record)
    annotate_read_report_attempt(target)
    finish_command_attempt(active, status="COMPLETED")
    return active.record.uid


def test_context_report_metadata_contains_only_locator_and_range(isolated_store):
    store = MemoryStore()
    target = ReadReportTarget(
        operation="find-conflicts",
        context_names=("team", "team/wiki"),
        target_names=("team",),
        selection_mode="SINGLE",
        ranges=("RECURSIVE",),
    )
    uid = _record(store, target, "2026-08-16T12:00:00+00:00")

    record = CommandAttemptLedger(isolated_store).load(uid)

    assert record.details == {"read_report": target.to_metadata()}
    encoded = str(record.details)
    assert "report body" not in encoded
    assert "provider" not in encoded
    assert "memory content" not in encoded


def test_find_duplicates_attempt_records_its_independent_exact_report_identity(
    isolated_store,
):
    store = MemoryStore()
    target = ReadReportTarget(
        operation="find-duplicates",
        context_names=("notes",),
        target_names=("notes",),
        selection_mode="SINGLE",
        ranges=("DIRECT",),
    )
    active = begin_command_attempt(
        store_dir=store.store_dir,
        operation="find-duplicates",
        stdin_tty=False,
        stdout_tty=False,
    )

    annotate_read_report_attempt(target)
    finish_command_attempt(active, status="COMPLETED")

    record = CommandAttemptLedger(isolated_store).load(active.record.uid)
    assert record.operation == "find-duplicates"
    assert record.details == {"read_report": target.to_metadata()}


def test_find_duplicates_attempt_rejects_redundancy_report_metadata(isolated_store):
    store = MemoryStore()
    target = ReadReportTarget(
        operation="find-redundancies",
        context_names=("notes",),
        target_names=("notes",),
        selection_mode="SINGLE",
        ranges=("DIRECT",),
    )
    active = begin_command_attempt(
        store_dir=store.store_dir,
        operation="find-duplicates",
        stdin_tty=False,
        stdout_tty=False,
    )

    with pytest.raises(CommandAttemptError, match="does not match"):
        annotate_read_report_attempt(target)
    finish_command_attempt(active, status="FAILED", failure_kind="contract")


def test_shared_recents_deduplicate_targets_and_keep_operations_separate(
    isolated_store,
):
    store = MemoryStore()
    target = ReadReportTarget(
        operation="summarize",
        context_names=("notes",),
        target_names=("notes",),
        selection_mode="SINGLE",
        ranges=("DIRECT", "RECURSIVE"),
    )
    _record(store, target, "2026-08-16T10:00:00+00:00")
    latest = _record(store, target, "2026-08-16T11:00:00+00:00")

    recents = read_report_recents(store, operation="summarize")

    assert len(recents) == 1
    assert recents[0].attempt_uid == latest
    assert recents[0].target == target
    assert read_report_recents(store, operation="dedun") == ()


def test_recent_launcher_returns_identity_and_never_an_execution_receipt(
    isolated_store,
):
    store = MemoryStore()
    target = ReadReportTarget(
        operation="dedun",
        context_names=("notes",),
        target_names=("notes",),
        selection_mode="SINGLE",
        ranges=("DIRECT",),
    )
    _record(store, target, "2026-08-16T11:00:00+00:00")
    recents = read_report_recents(store, operation="dedun")
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_read_report_recent(
            recents,
            operation="dedun",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == target
    assert not hasattr(selected, "argv")


def test_empty_recent_catalog_skips_the_launcher():
    selected = choose_read_report_recent((), operation="summarize", require_tty=False)

    assert isinstance(selected, ReadReportSelectTarget)


def test_profile_recent_has_one_exclusive_virtual_target():
    target = ReadReportTarget(
        operation="find-conflicts",
        context_names=("team", "team/wiki"),
        target_names=(),
        selection_mode="MULTIPLE",
        ranges=("DIRECT",),
        profile_selected=True,
    )

    assert target.profile_selected is True
    with pytest.raises(ReadReportError, match="cannot retain ordinary target"):
        ReadReportTarget(
            operation="find-conflicts",
            context_names=("team", "team/wiki"),
            target_names=("team",),
            selection_mode="MULTIPLE",
            ranges=("DIRECT",),
            profile_selected=True,
        )


def test_selected_recent_is_revalidated_against_the_ledger(isolated_store):
    store = MemoryStore()
    target = ReadReportTarget(
        operation="summarize",
        context_names=("notes",),
        target_names=("notes",),
        selection_mode="SINGLE",
        ranges=("DIRECT",),
    )
    _record(store, target, "2026-08-16T11:00:00+00:00")
    recent = read_report_recents(store, operation="summarize")[0]
    ledger = CommandAttemptLedger(store.store_dir)
    record = ledger.load(recent.attempt_uid)
    changed = ReadReportTarget(
        operation="summarize",
        context_names=("other",),
        target_names=("other",),
        selection_mode="SINGLE",
        ranges=("DIRECT",),
    )
    ledger.replace(replace(record, details={"read_report": changed.to_metadata()}))

    with pytest.raises(ReadReportError, match="changed"):
        revalidate_read_report_recent(store, recent)
