"""Saved-session catalog and picker contracts for Context Meld."""
from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.meld import _session_command
from memcommit.adapters.console.commands.meld.sessions import (
    MeldSessionCatalogError,
    list_meld_session_catalog,
    reload_selected_meld_session,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import SessionNewReceipt, SessionOpenReceipt
from memcommit.application.operations.meld.model import MeldSession
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def _save_directional_session(
    store: MemoryStore,
    *,
    namespace: str,
) -> MeldSession:
    incoming = ops.init(f"{namespace}/incoming")
    ops.add(incoming, f"Incoming knowledge for {namespace}.")
    baseline = ops.init(f"{namespace}/baseline")
    ops.add(baseline, f"Baseline knowledge for {namespace}.")
    store.save(incoming)
    store.save(baseline)
    session = MeldSession.create_directional(incoming, baseline)
    store.save_meld_session(session, expected_session_digest=None)
    return session


def test_meld_catalog_is_recently_modified_and_grouped_by_target(
    isolated_store,
) -> None:
    store = MemoryStore()
    older = _save_directional_session(store, namespace="catalog/older")
    newer = _save_directional_session(store, namespace="catalog/newer")
    older_path = store._meld_session_path(older.target.context_uid)
    newer_path = store._meld_session_path(newer.target.context_uid)
    os.utime(older_path, (1_700_000_000, 1_700_000_000))
    os.utime(newer_path, (1_800_000_000, 1_800_000_000))

    entries = list_meld_session_catalog(store)

    assert [entry.key for entry in entries] == [
        newer.target.context_uid,
        older.target.context_uid,
    ]
    newest = entries[0]
    assert newest.group == "catalog/newer/baseline"
    assert newest.title == (
        "catalog/newer/incoming → catalog/newer/baseline"
    )
    assert newest.status == "PENDING_ANALYSIS"
    assert "Directional · INCOMING → BASELINE / TARGET" in (
        newest.subtitle
    )
    assert "from file metadata" in newest.detail
    assert newest.reopen_argv == (
        "mem",
        "meld",
        "catalog/newer/incoming",
        "catalog/newer/baseline",
    )


def test_directional_meld_catalog_preserves_both_descendant_ranges(
    isolated_store,
) -> None:
    store = MemoryStore()
    incoming = ops.init("catalog/scoped/incoming")
    baseline = ops.init("catalog/scoped/baseline")
    ops.add(incoming, "Incoming scoped knowledge.")
    ops.add(baseline, "Baseline scoped knowledge.")
    store.save(incoming)
    store.save(baseline)
    session = MeldSession.create_directional(
        incoming,
        baseline,
        incoming_descendants=True,
        baseline_descendants=True,
    )
    store.save_meld_session(session, expected_session_digest=None)

    entry = list_meld_session_catalog(store)[0]

    assert entry.reopen_argv == (
        "mem",
        "meld",
        "catalog/scoped/incoming",
        "catalog/scoped/baseline",
        "--left-descendants",
        "--right-descendants",
    )
    assert _session_command(session) == (
        "mem meld catalog/scoped/incoming catalog/scoped/baseline "
        "--left-descendants --right-descendants"
    )


def test_symmetric_meld_catalog_reopens_with_explicit_result(
    isolated_store,
) -> None:
    store = MemoryStore()
    left = ops.init("catalog/symmetric/left")
    right = ops.init("catalog/symmetric/right")
    target = ops.init("catalog/symmetric/result")
    ops.add(left, "Left peer knowledge.")
    ops.add(right, "Right peer knowledge.")
    for context in (left, right, target):
        store.save(context)
    session = MeldSession.create_symmetric(left, right, target)
    store.save_meld_session(session, expected_session_digest=None)

    entry = list_meld_session_catalog(store)[0]

    assert entry.reopen_argv == (
        "mem",
        "meld",
        left.name,
        right.name,
        "--to",
        target.name,
    )
    assert _session_command(session) == (
        "mem meld catalog/symmetric/left catalog/symmetric/right "
        "--to catalog/symmetric/result"
    )


def test_meld_catalog_reload_rejects_same_key_replacement(
    isolated_store,
) -> None:
    store = MemoryStore()
    original = _save_directional_session(store, namespace="catalog/race")
    entry = list_meld_session_catalog(store)[0]
    store.delete_meld_session(original.target.context_uid)
    replacement = MeldSession.create_directional(
        store.load_direct("catalog/race/incoming"),
        store.load_direct("catalog/race/baseline"),
    )
    store.save_meld_session(replacement, expected_session_digest=None)

    with pytest.raises(
        MeldSessionCatalogError,
        match="changed while the list was open",
    ):
        reload_selected_meld_session(store, entry)


def test_meld_session_picker_reports_an_empty_catalog(
    isolated_store,
) -> None:
    result = runner.invoke(app, ["meld", "--sessions"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "No saved Meld sessions."


def test_meld_session_picker_reopens_without_provider_or_mutation(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    session = _save_directional_session(store, namespace="catalog/open")
    session_path = store._meld_session_path(session.target.context_uid)
    session_before = session_path.read_bytes()
    contexts_before = {
        frame.context_name: store._context_file(frame.context_name).read_bytes()
        for frame in session.frames
    }

    def choose(entries, **kwargs):
        assert kwargs["title"] == "MELD SESSIONS · RECENTLY MODIFIED"
        assert kwargs["new_receipt"] == SessionNewReceipt(
            kind="meld",
            argv=("mem", "meld"),
        )
        assert len(entries) == 1
        option = entries[0]
        assert option.group == session.target.context_name
        return SessionOpenReceipt(
            kind="meld",
            key=option.key,
            argv=option.reopen_argv,
        )

    monkeypatch.setattr("memcommit.adapters.console.commands.meld.choose_session", choose)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.meld.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("A provider was opened during read-only resume.")
        ),
    )

    result = runner.invoke(app, ["meld", "--sessions"])

    assert result.exit_code == 0, result.output
    assert "MELD PENDING · DIRECTIONAL" in result.output
    assert f"IMPACT · mem impact meld --session {session.uid}" in result.output
    assert "Resumed without calling the semantic provider" in result.output
    assert session_path.read_bytes() == session_before
    assert {
        name: store._context_file(name).read_bytes()
        for name in contexts_before
    } == contexts_before
    assert store.list_checkpoints(session.target.context_name) == []


def test_meld_session_picker_revalidates_after_selection(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    session = _save_directional_session(store, namespace="catalog/delete")

    def choose(entries, **kwargs):
        option = entries[0]
        store.delete_meld_session(option.key)
        return SessionOpenReceipt(
            kind="meld",
            key=option.key,
            argv=option.reopen_argv,
        )

    monkeypatch.setattr("memcommit.adapters.console.commands.meld.choose_session", choose)

    result = runner.invoke(app, ["meld", "--sessions"])

    assert result.exit_code == 1
    assert "selected Meld session no longer exists" in result.output
    assert store.load_meld_session(session.target.context_uid) is None


def test_meld_sessions_rejects_explicit_route_or_action(
    isolated_store,
) -> None:
    result = runner.invoke(
        app,
        ["meld", "left", "right", "--sessions"],
    )

    assert result.exit_code == 2
    assert "cannot be combined" in result.output
