"""Aggregate saved artifacts that can be reopened through ``mem impact``.

The catalog is a presentation-only union.  Atomize, Meld, Sever, and Update
retain their own persistence and reload checks; selecting a row returns only
the frozen operation kind and artifact UID for redispatch through Impact.
Process-local Impact routes are deliberately absent because they have no
durable artifact to reopen.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import sys

from memcommit.adapters.console.commands.atomize.records import atomize_record_entries
from memcommit.adapters.console.terminal.components.operation_launcher.location import (
    session_picker_location,
)
from memcommit.adapters.console.commands.meld.sessions import list_meld_session_catalog
from memcommit.adapters.console.commands.sever.sessions import (
    list_sever_session_catalog,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.core.context_targeting.uid_locator import (
    UidLocatorError,
    resolve_exact_or_unique_uid,
)
from memcommit.application.operations.sever.session_store import SeverSessionStore
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.operations.update.receipt_repository import (
    UpdateReceiptRepository,
)


IMPACT_SESSION_KINDS = ("atomize", "meld", "sever", "update")


def select_saved_session(
    entries: tuple[SessionPickerEntry, ...],
    *,
    kind: str,
    title: str,
    session_uid: str | None,
) -> SessionPickerEntry | None:
    """Resolve one saved UID/prefix or one frozen TTY choice."""

    if session_uid is not None:
        try:
            return resolve_exact_or_unique_uid(
                entries,
                session_uid,
                uid=lambda entry: entry.key,
                label=f"Saved {kind.title()} Impact artifact",
            )
        except UidLocatorError as error:
            raise ValueError(str(error)) from error
    if not entries:
        raise ValueError(f"No saved {kind.title()} Impact artifacts are available.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        if len(entries) == 1:
            return entries[0]
        raise ValueError(
            f"Several saved {kind.title()} artifacts are available; pass --session UID."
        )
    receipt = choose_session(entries, title=title)
    if receipt is None:
        return None
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != kind:
        raise ValueError("Impact session picker returned an invalid receipt.")
    selected = next((entry for entry in entries if entry.key == receipt.key), None)
    if selected is None or selected.reopen_argv != receipt.argv:
        raise ValueError("Impact session picker returned a stale receipt.")
    return selected


def _artifact_timestamp(path, *, fallback: str) -> float:
    """Prefer durable file activity while retaining a serialized fallback."""

    timestamp = datetime.fromisoformat(fallback).timestamp()
    try:
        if path.is_file() and not path.is_symlink():
            timestamp = max(timestamp, path.stat().st_mtime)
    except FileNotFoundError:
        # Exact redispatch reloads the artifact after selection.  A concurrent
        # deletion therefore becomes a normal unavailable-session failure.
        pass
    return timestamp


def _impact_entry(
    entry: SessionPickerEntry,
    *,
    operation: str | None = None,
) -> SessionPickerEntry:
    """Orient one operation-owned row without changing its saved identity."""

    kind = operation or entry.kind
    label = kind.replace("_", " ").replace("-", " ").upper()
    return replace(
        entry,
        title=f"{label} · {entry.title}",
        detail="\n".join(
            (
                f"{label} IMPACT",
                f"State: {entry.status}",
                f"Context: {entry.group}",
                f"Summary: {entry.subtitle or '(none)'}",
                "",
                entry.detail,
                "",
                "Enter inspects this exact saved artifact through Impact.",
                "Opening the artifact does not call a semantic provider or "
                "apply Memory changes.",
                "Any later Apply handoff remains explicit and operation-owned.",
            )
        ),
        # The exact argv is control data validated after selection.  Hiding it
        # avoids presenting the launcher's defensive argument array as report
        # content while still making the UID authoritative.
        reopen_argv=("mem", "impact", kind, "--session", entry.key),
        detail_only=True,
    )


def _meld_entries(store: MemoryStore) -> tuple[SessionPickerEntry, ...]:
    return tuple(
        _impact_entry(
            SessionPickerEntry(
                kind="meld",
                key=entry.session_uid,
                title=entry.title,
                status=entry.status,
                subtitle=entry.subtitle,
                group=entry.group,
                sort_timestamp=entry.modified_timestamp,
                detail=entry.detail,
                reopen_argv=entry.reopen_argv,
            )
        )
        for entry in list_meld_session_catalog(store)
    )


def _update_entry(store: MemoryStore) -> SessionPickerEntry | None:
    session = store.load_staged_update()
    path = store.staged_update_file
    if session is None:
        session = store.load_impact_plan()
        path = store.impact_plan_file
    if session is None:
        return None
    return _impact_entry(
        SessionPickerEntry(
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
                "The singleton Update or directional Impact receipt remains "
                "operation-owned."
            ),
            reopen_argv=("mem", "impact", "update", "--session", session.uid),
        )
    )


def _retained_update_entries(store: MemoryStore) -> tuple[SessionPickerEntry, ...]:
    receipts = UpdateReceiptRepository(store)
    current = store.load_staged_update() or store.load_impact_plan()
    current_uid = current.uid if current is not None else None
    return tuple(
        _impact_entry(
            SessionPickerEntry(
                kind="update",
                key=session.uid,
                title=f"{session.source_name} → {session.target_name}",
                status=session.status.upper(),
                subtitle=(
                    f"{len(session.operations)} retained "
                    f"{'change' if len(session.operations) == 1 else 'changes'}"
                ),
                group=session.target_name,
                sort_timestamp=_artifact_timestamp(
                    receipts.path(session.uid),
                    fallback=session.application.applied_at,
                ),
                detail=(
                    f"Session {session.uid}\n"
                    f"Source {session.source_name}\n"
                    f"Target {session.target_name}\n"
                    "Immutable completed Update evidence."
                ),
                reopen_argv=(
                    "mem",
                    "impact",
                    "update",
                    "--session",
                    session.uid,
                ),
            )
        )
        for session in receipts.list()
        if session.uid != current_uid
    )


def impact_session_entries(store: MemoryStore) -> tuple[SessionPickerEntry, ...]:
    """Return every durable artifact currently inspectable by Impact."""

    entries: list[SessionPickerEntry] = []
    entries.extend(_impact_entry(entry) for entry in atomize_record_entries(store))
    entries.extend(_meld_entries(store))
    entries.extend(
        _impact_entry(entry.picker_entry)
        for entry in list_sever_session_catalog(SeverSessionStore(store))
    )
    entries.extend(_retained_update_entries(store))
    update_entry = _update_entry(store)
    if update_entry is not None:
        entries.append(update_entry)
    return tuple(entries)


def choose_impact_session(
    store: MemoryStore,
    *,
    kinds: tuple[str, ...] | None = None,
    title: str = "MEM IMPACT · SAVED ANALYSES",
) -> SessionOpenReceipt | None:
    """Choose one frozen Impact artifact without opening or mutating it."""

    selected_kinds = IMPACT_SESSION_KINDS if kinds is None else kinds
    if (
        not selected_kinds
        or len(set(selected_kinds)) != len(selected_kinds)
        or any(kind not in IMPACT_SESSION_KINDS for kind in selected_kinds)
    ):
        raise ValueError("Impact session launcher received invalid operation kinds.")
    entries = tuple(
        entry for entry in impact_session_entries(store) if entry.kind in selected_kinds
    )
    receipt = choose_session(
        entries,
        title=title,
        location=session_picker_location(store),
        catalog_label="saved Impact analyses",
        enter_action="inspect",
    )
    if receipt is None:
        return None
    if not isinstance(receipt, SessionOpenReceipt):
        raise ValueError("Impact session launcher returned an invalid receipt.")
    selected = next(
        (
            entry
            for entry in entries
            if entry.kind == receipt.kind and entry.key == receipt.key
        ),
        None,
    )
    if selected is None or selected.reopen_argv != receipt.argv:
        raise ValueError("Impact session launcher returned a stale receipt.")
    return receipt


__all__ = [
    "IMPACT_SESSION_KINDS",
    "choose_impact_session",
    "impact_session_entries",
    "select_saved_session",
]
