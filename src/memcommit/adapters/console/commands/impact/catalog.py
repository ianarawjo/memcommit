"""Aggregate saved artifacts that can be reopened through ``mem impact``.

The catalog is a presentation-only union.  Atomize and Sever
retain their own persistence and reload checks; selecting a row returns only
the frozen operation kind and artifact UID for redispatch through Impact.
Process-local Impact routes are deliberately absent because they have no
durable artifact to reopen.
"""

from __future__ import annotations

from dataclasses import replace
import sys

from memcommit.adapters.console.commands.atomize.records import atomize_record_entries
from memcommit.adapters.console.terminal.components.operation_launcher.location import (
    session_picker_location,
)
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
from memcommit.persistence.store import ProfileStore


IMPACT_SESSION_KINDS = ("atomize", "sever")


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


def _impact_entry(
    entry: SessionPickerEntry,
    *,
    operation: str | None = None,
) -> SessionPickerEntry:
    """Orient one operation-owned row without changing its saved identity."""

    kind = operation or entry.kind
    public_name = kind
    label = public_name.replace("_", " ").replace("-", " ").upper()
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
        reopen_argv=("mem", "impact", public_name, "--session", entry.key),
        detail_only=True,
    )


def impact_session_entries(store: ProfileStore) -> tuple[SessionPickerEntry, ...]:
    """Return every durable artifact currently inspectable by Impact."""

    entries: list[SessionPickerEntry] = []
    entries.extend(_impact_entry(entry) for entry in atomize_record_entries(store))
    entries.extend(
        _impact_entry(entry.picker_entry)
        for entry in list_sever_session_catalog(SeverSessionStore(store))
    )
    return tuple(entries)


def choose_impact_session(
    store: ProfileStore,
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
