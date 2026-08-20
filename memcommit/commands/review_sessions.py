"""Aggregate saved semantic-review work for the bare Review launcher.

The launcher is a presentation-only union.  Every operation keeps ownership of
its state, persistence, reload checks, and review surface; selecting a row only
returns the exact frozen kind/key receipt to ``mem review`` for redispatch.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from memcommit.applied_checkpoint_review import (
    CHECKPOINT_REVIEW_OPERATIONS,
    list_applied_checkpoint_reviews,
)
from memcommit.commands.audit_sessions import audit_session_entries
from memcommit.commands.atomize_sessions import atomize_session_entries
from memcommit.commands.compare_sessions import comparison_session_entries
from memcommit.commands.ground_session_picker import session_picker_location
from memcommit.commands.meld_sessions import list_meld_session_catalog
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.commands.sever_sessions import list_sever_session_catalog
from memcommit.sever_store import SeverSessionStore
from memcommit.quality_audit_store import QualityAuditStore
from memcommit.store import MemoryStore


SAVED_REVIEW_KIND = "saved-review"


def _review_detail(entry: SessionPickerEntry, *, operation: str) -> str:
    """Describe one existing session without exposing argv-array mechanics."""

    lines = (
        f"{operation} REVIEW",
        f"State: {entry.status}",
        f"Context: {entry.group}",
        f"Summary: {entry.subtitle or '(none)'}",
        "",
        entry.detail,
        "",
        "Enter views this saved session in its existing review screen.",
        "Review does not apply Memory changes or create a checkpoint.",
    )
    return "\n".join(lines)


def _review_entry(
    entry: SessionPickerEntry,
    *,
    operation: str | None = None,
) -> SessionPickerEntry:
    """Add operation orientation while preserving the operation-owned state."""

    label = (operation or entry.kind).replace("_", " ").replace("-", " ").upper()
    return replace(
        entry,
        title=f"{label} · {entry.title}",
        detail=_review_detail(entry, operation=label),
        # The aggregate Review launcher should explain review state, not leak
        # the picker's defensive argv-index representation ([0], [1], ...).
        # The frozen argv remains on the receipt for identity validation.
        detail_only=True,
    )


def _artifact_timestamp(path, *, fallback: str) -> float:
    """Use durable file activity as presentation time when it is available."""

    timestamp = datetime.fromisoformat(fallback).timestamp()
    try:
        if path.is_file() and not path.is_symlink():
            timestamp = max(timestamp, path.stat().st_mtime)
    except FileNotFoundError:
        # Selection reloads the authoritative record.  A concurrent deletion
        # only makes this frozen row fail its normal post-picker validation.
        pass
    return timestamp


def _saved_update_entry(store: MemoryStore) -> SessionPickerEntry | None:
    session = store.load_staged_update()
    path = store.staged_update_file
    if session is None:
        session = store.load_impact_plan()
        path = store.impact_plan_file
    if session is None:
        return None
    if session.status not in {"applied", "undone"}:
        return None
    entry = SessionPickerEntry(
        kind="update",
        key=session.uid,
        title=f"{session.source_name} → {session.target_name}",
        status=session.status.upper(),
        subtitle=(
            f"{len(session.operations)} planned "
            f"{'change' if len(session.operations) == 1 else 'changes'}"
        ),
        group=session.target_name,
        sort_timestamp=_artifact_timestamp(path, fallback=session.created_at),
        detail=(
            f"Session {session.uid}\n"
            f"Source {session.source_name}\n"
            f"Target {session.target_name}\n"
            "The singleton Update or Impact receipt remains operation-owned."
        ),
        reopen_argv=("mem", "review", "update", "--session", session.uid),
    )
    return _review_entry(entry)


def _checkpoint_review_entries(store: MemoryStore) -> tuple[SessionPickerEntry, ...]:
    entries: list[SessionPickerEntry] = []
    for operation in sorted(CHECKPOINT_REVIEW_OPERATIONS):
        for record in list_applied_checkpoint_reviews(store, operation):
            entry = SessionPickerEntry(
                kind=operation,
                key=record.checkpoint_uid,
                title=f"{record.context_name} · {record.checkpoint_uid[:8]}",
                status="APPLIED",
                subtitle=record.description,
                group=record.context_name,
                sort_timestamp=datetime.fromisoformat(record.timestamp).timestamp(),
                detail=(
                    f"Receipt {record.checkpoint_uid}\n"
                    f"Completed {record.timestamp}\n\n"
                    "Immutable post-application evidence."
                ),
                reopen_argv=(
                    "mem",
                    "review",
                    operation,
                    "--receipt",
                    record.checkpoint_uid,
                ),
            )
            entries.append(_review_entry(entry))
    return tuple(entries)


def _saved_review_entry(store: MemoryStore) -> SessionPickerEntry | None:
    """Project the honest singleton ReviewSession as one launcher row."""

    session = store.load_review_session()
    if session is None:
        return None
    try:
        modified = store.review_session_file.stat().st_mtime
    except FileNotFoundError:
        # The returned row will fail exact reload if selected after deletion.
        modified = 0.0
    operation = session.kind.replace("_", " ").replace("-", " ").upper()
    total = len(session.items)
    status = (
        f"{session.answered_count}/{total} ANSWERED" if total else "NO REVIEW ITEMS"
    )
    entry = SessionPickerEntry(
        # Keep this distinct from the newer Context-bound Atomize workbench.
        # Both may legitimately exist and retain different reviewer evidence.
        kind=SAVED_REVIEW_KIND,
        key=session.uid,
        title=f"{operation} · {session.context_name}",
        status=status,
        subtitle=f"{total} review {'item' if total == 1 else 'items'}",
        group=session.context_name,
        sort_timestamp=modified,
        detail=(
            f"{operation} REVIEW\n"
            f"State: {status}\n"
            f"Context: {session.context_name}\n"
            f"Review session: {session.uid}\n\n"
            "Enter resumes this saved ReviewSession in its existing review screen.\n"
            "Review does not apply Memory changes or create a checkpoint."
        ),
        # This internal receipt remains hidden by detail_only.  The singleton
        # UID, not a displayed shell command, is authoritative after selection.
        reopen_argv=("mem", "review"),
        detail_only=True,
    )
    return entry


def review_session_entries(store: MemoryStore) -> tuple[SessionPickerEntry, ...]:
    """Return every saved session that the Review host can currently view."""

    entries: list[SessionPickerEntry] = []
    entries.extend(_checkpoint_review_entries(store))
    entries.extend(
        _review_entry(entry)
        for entry in audit_session_entries(QualityAuditStore(store))
    )
    entries.extend(
        _review_entry(entry)
        for entry in atomize_session_entries(store)
        if entry.status == "APPLIED"
    )
    entries.extend(_review_entry(entry) for entry in comparison_session_entries(store))
    entries.extend(
        _review_entry(entry)
        for entry in (
            catalog_entry.picker_entry
            for catalog_entry in list_sever_session_catalog(SeverSessionStore(store))
            if catalog_entry.picker_entry.status == "APPLIED"
        )
    )
    entries.extend(
        _review_entry(
            SessionPickerEntry(
                kind="meld",
                key=catalog_entry.session_uid,
                title=catalog_entry.title,
                status=catalog_entry.status,
                subtitle=catalog_entry.subtitle,
                group=catalog_entry.group,
                sort_timestamp=catalog_entry.modified_timestamp,
                detail=catalog_entry.detail,
                reopen_argv=catalog_entry.reopen_argv,
            )
        )
        for catalog_entry in list_meld_session_catalog(store)
        if catalog_entry.status == "APPLIED"
    )
    update_entry = _saved_update_entry(store)
    if update_entry is not None:
        entries.append(update_entry)
    saved_review = _saved_review_entry(store)
    if saved_review is not None:
        entries.append(saved_review)
    return tuple(entries)


def choose_review_session(store: MemoryStore) -> SessionOpenReceipt | None:
    """Choose one frozen saved review session without opening or mutating it."""

    entries = review_session_entries(store)
    receipt = choose_session(
        entries,
        title="MEM REVIEW · SAVED SESSIONS",
        location=session_picker_location(store),
        catalog_label="saved review sessions",
        enter_action="view",
    )
    if receipt is None:
        return None
    if not isinstance(receipt, SessionOpenReceipt):
        raise ValueError("Review session launcher returned an invalid receipt.")
    selected = next(
        (
            entry
            for entry in entries
            if entry.kind == receipt.kind and entry.key == receipt.key
        ),
        None,
    )
    if selected is None or selected.reopen_argv != receipt.argv:
        raise ValueError("Review session launcher returned a stale receipt.")
    return receipt
