"""Aggregate Review launcher contracts."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from typer.testing import CliRunner

import memcommit.commands.review.command as review_command
import memcommit.commands.review.sessions as review_sessions
import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionOpenReceipt,
    SessionPickerEntry,
)
from memcommit.review import ReviewSession, direct_context_digest
from memcommit.store import MemoryStore


runner = CliRunner()


def _entry(
    kind: str,
    key: str,
    *,
    status: str,
    timestamp: float,
) -> SessionPickerEntry:
    return SessionPickerEntry(
        kind=kind,
        key=key,
        title=f"{kind}-target",
        status=status,
        subtitle=f"{kind} summary",
        group=f"{kind}/context",
        sort_timestamp=timestamp,
        detail=f"{kind} operation detail",
        reopen_argv=("mem", kind, key),
    )


def test_review_projection_preserves_operation_state_and_hides_argv_indexes():
    source = _entry(
        "atomize",
        "analysis-one",
        status="AWAITING_REPLY",
        timestamp=3,
    )

    projected = review_sessions._review_entry(source)

    assert projected.status == "AWAITING_REPLY"
    assert projected.title == "ATOMIZE · atomize-target"
    assert projected.reopen_argv is source.reopen_argv
    assert projected.detail_only
    assert "State: AWAITING_REPLY" in projected.detail
    assert "existing review screen" in projected.detail
    assert "[0]" not in projected.detail
    assert "NOT EXECUTED" not in projected.detail


def test_aggregate_catalog_excludes_nonterminal_execution_states(
    isolated_store,
    monkeypatch,
):
    atomize = _entry("atomize", "a", status="READY_TO_APPLY", timestamp=6)
    compare = _entry("compare", "c", status="CURRENT", timestamp=5)
    sever = _entry("sever", "s", status="OPEN", timestamp=4)
    meld = _entry("meld", "m", status="APPLIED", timestamp=3)

    class SeverCatalog:
        picker_entry = sever

    class MeldCatalog:
        session_uid = meld.key
        title = meld.title
        status = meld.status
        subtitle = meld.subtitle
        group = meld.group
        modified_timestamp = meld.sort_timestamp
        detail = meld.detail
        reopen_argv = meld.reopen_argv

    monkeypatch.setattr(
        review_sessions,
        "atomize_session_entries",
        lambda _store: (atomize,),
    )
    monkeypatch.setattr(
        review_sessions,
        "comparison_session_entries",
        lambda _store: (compare,),
    )
    monkeypatch.setattr(
        review_sessions,
        "list_sever_session_catalog",
        lambda _sessions: (SeverCatalog(),),
    )
    monkeypatch.setattr(
        review_sessions,
        "list_meld_session_catalog",
        lambda _store: (MeldCatalog(),),
    )
    monkeypatch.setattr(
        review_sessions,
        "_saved_update_entry",
        lambda _store: None,
    )
    monkeypatch.setattr(
        review_sessions,
        "_saved_review_entry",
        lambda _store: None,
    )

    entries = review_sessions.review_session_entries(MemoryStore())

    assert [(entry.kind, entry.status) for entry in entries] == [
        ("compare", "CURRENT"),
        ("meld", "APPLIED"),
    ]
    assert all(entry.detail_only for entry in entries)


def test_global_review_singleton_is_one_honest_session_row(isolated_store):
    store = MemoryStore()
    ctx = ops.init("review/empty")
    store.save(ctx)
    session = ReviewSession(
        uid=str(uuid.uuid4()),
        kind="ambiguities",
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=direct_context_digest(ctx),
        items=(),
    )
    store.save_review_session(session)

    entry = review_sessions._saved_review_entry(store)

    assert entry is not None
    assert entry.kind == review_sessions.SAVED_REVIEW_KIND
    assert entry.key == session.uid
    assert entry.status == "NO REVIEW ITEMS"
    assert entry.title == "AMBIGUITIES · review/empty"
    assert entry.detail_only
    assert "[0]" not in entry.detail


def test_bare_tty_review_dispatches_selected_operation_by_exact_key(
    isolated_store,
    monkeypatch,
):
    analysis_uid = str(uuid.uuid4())
    receipt = SessionOpenReceipt(
        kind="compare",
        key=analysis_uid,
        argv=("mem", "compare", analysis_uid),
    )
    captured = {}
    monkeypatch.setattr(review_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        review_command,
        "choose_review_session",
        lambda _store: receipt,
    )
    monkeypatch.setattr(
        review_command,
        "_run_compare_report",
        lambda _store, *, session_uid, snapshot: captured.update(
            session_uid=session_uid,
            snapshot=snapshot,
        ),
    )

    result = runner.invoke(app, ["review"])

    assert result.exit_code == 0, result.output
    assert captured == {"session_uid": analysis_uid, "snapshot": False}


def test_bare_tty_review_passes_exact_atomize_analysis_identity(
    isolated_store,
    monkeypatch,
):
    analysis_uid = str(uuid.uuid4())
    receipt = SessionOpenReceipt(
        kind="atomize",
        key=analysis_uid,
        argv=("mem", "atomize", analysis_uid),
    )
    captured = {}
    monkeypatch.setattr(review_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        review_command,
        "choose_review_session",
        lambda _store: receipt,
    )
    monkeypatch.setattr(
        review_command,
        "_run_atomize_workbench",
        lambda **kwargs: captured.update(kwargs),
    )

    result = runner.invoke(app, ["review"])

    assert result.exit_code == 0, result.output
    assert captured["expected_analysis_uid"] == analysis_uid
    assert captured["context_name"] is None
    assert captured["replace"] is False


def test_empty_or_cancelled_tty_launcher_does_not_fall_back_to_atomize(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(review_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        review_command,
        "choose_review_session",
        lambda _store: None,
    )
    monkeypatch.setattr(
        review_command,
        "_run_atomize_workbench",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("launcher cancellation must not enter Atomize")
        ),
    )

    result = runner.invoke(app, ["review"])

    assert result.exit_code == 0, result.output
    assert result.output == "Review selection cancelled.\n"


def test_applied_sever_selection_still_opens_read_only_review(
    isolated_store,
    monkeypatch,
):
    import memcommit.commands.sever.command as sever_command
    import memcommit.commands.sever.sessions as sever_sessions
    import memcommit.review_report_adapters as adapters

    session_uid = str(uuid.uuid4())
    picker_entry = _entry(
        "sever",
        session_uid,
        status="APPLIED · SOURCE UNCHANGED",
        timestamp=1,
    )
    catalog_entry = SimpleNamespace(picker_entry=picker_entry)
    applied = SimpleNamespace(state="APPLIED")
    controller = object()
    shown = {}
    monkeypatch.setattr(review_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        sever_sessions,
        "list_sever_session_catalog",
        lambda _sessions: (catalog_entry,),
    )
    monkeypatch.setattr(
        sever_sessions,
        "reload_selected_sever_session",
        lambda _sessions, _entry: applied,
    )
    monkeypatch.setattr(
        adapters,
        "sever_review_report",
        lambda _session: controller,
    )
    monkeypatch.setattr(
        sever_command,
        "run_sever_review",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("an applied Sever has no editable decision loop")
        ),
    )
    monkeypatch.setattr(
        review_command,
        "_show_operation_review",
        lambda value, *, snapshot: shown.update(
            controller=value,
            snapshot=snapshot,
        ),
    )

    review_command._run_sever_report(
        MemoryStore(),
        session_uid=session_uid,
        snapshot=False,
    )

    assert shown == {"controller": controller, "snapshot": False}


def test_applied_meld_selection_still_opens_read_only_review(
    isolated_store,
    monkeypatch,
):
    import memcommit.commands.meld.command as meld_command
    import memcommit.commands.meld.sessions as meld_sessions
    import memcommit.review_report_adapters as adapters

    session_uid = str(uuid.uuid4())
    catalog_entry = SimpleNamespace(
        session_uid=session_uid,
        title="left + right → target",
        status="APPLIED",
        subtitle="Symmetric · 2 turns",
        group="target",
        modified_timestamp=1,
        detail="Applied Meld",
        reopen_argv=("mem", "meld", "left", "right"),
    )
    applied = SimpleNamespace(state="APPLIED")
    controller = object()
    shown = {}
    monkeypatch.setattr(review_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        meld_sessions,
        "list_meld_session_catalog",
        lambda _store: (catalog_entry,),
    )
    monkeypatch.setattr(
        meld_sessions,
        "reload_selected_meld_session",
        lambda _store, _entry: applied,
    )
    monkeypatch.setattr(
        adapters,
        "meld_review_report",
        lambda _session: controller,
    )
    monkeypatch.setattr(
        meld_command,
        "run_meld_review",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("an applied Meld has no editable turn loop")
        ),
    )
    monkeypatch.setattr(
        review_command,
        "_show_operation_review",
        lambda value, *, snapshot: shown.update(
            controller=value,
            snapshot=snapshot,
        ),
    )

    review_command._run_meld_report(
        MemoryStore(),
        session_uid=session_uid,
        snapshot=False,
    )

    assert shown == {"controller": controller, "snapshot": False}
