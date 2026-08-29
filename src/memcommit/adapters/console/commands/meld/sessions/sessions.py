"""Read-only catalog projections for saved Context Meld sessions.

The catalog deliberately keeps discovery separate from opening.  A picker may
show metadata from this snapshot, but the command must reload the selected
target-scoped record and compare its identity before entering the workbench.
"""
from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from memcommit.application.operations.meld.model import MeldSession, meld_canonical_digest
from memcommit.persistence.store import MemoryStore


class MeldSessionCatalogError(ValueError):
    """A saved Meld catalog cannot be read or safely reopened."""


@dataclass(frozen=True)
class MeldSessionCatalogEntry:
    """One immutable picker projection and its revalidation evidence."""

    key: str
    target_context_uid: str
    session_uid: str
    session_digest: str
    title: str
    status: str
    subtitle: str
    group: str
    modified_timestamp: float
    modified_at: str
    detail: str
    reopen_argv: tuple[str, ...]
    archived: bool


def _canonical_storage_key(path: Path) -> str:
    try:
        canonical = str(uuid.UUID(path.stem))
    except (AttributeError, TypeError, ValueError) as error:
        raise MeldSessionCatalogError(
            f"Saved Meld session has an invalid storage key: {path.name}"
        ) from error
    if canonical != path.stem:
        raise MeldSessionCatalogError(
            f"Saved Meld session has an invalid storage key: {path.name}"
        )
    return canonical


def _session_route(session: MeldSession) -> tuple[str, str]:
    left, right = session.frames
    if session.mode == "DIRECTIONAL":
        return (
            f"{left.context_name} → {right.context_name}",
            "Directional · INCOMING → BASELINE / TARGET",
        )
    return (
        (
            f"{left.context_name} + {right.context_name} → "
            f"{session.target.context_name}"
        ),
        "Symmetric · PEER + PEER → TARGET",
    )


def _reopen_argv(session: MeldSession) -> tuple[str, ...]:
    left, right = session.frames
    left_scope = ("--left-descendants",) if left.include_descendants else ()
    right_scope = (
        ("--right-descendants",) if right.include_descendants else ()
    )
    if session.mode == "DIRECTIONAL":
        return (
            "mem",
            "meld",
            left.context_name,
            right.context_name,
            *left_scope,
            *right_scope,
        )
    return (
        "mem",
        "meld",
        left.context_name,
        right.context_name,
        *left_scope,
        *right_scope,
        "--to",
        session.target.context_name,
    )


def _catalog_entry(
    path: Path,
    session: MeldSession,
    *,
    key: str,
    archived: bool,
) -> MeldSessionCatalogEntry:
    if archived:
        if key != session.uid or path.stem != session.uid:
            raise MeldSessionCatalogError(
                "Retained Meld session does not match its session storage key."
            )
    elif session.target.context_uid != key:
        raise MeldSessionCatalogError(
            "Saved Meld session does not match its target storage key."
        )
    try:
        stat = path.stat()
    except OSError as error:
        raise MeldSessionCatalogError(
            "Saved Meld session changed during catalog discovery."
        ) from error
    title, route_kind = _session_route(session)
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    turn_count = len(session.turns)
    return MeldSessionCatalogEntry(
        key=key,
        target_context_uid=session.target.context_uid,
        session_uid=session.uid,
        session_digest=meld_canonical_digest(session.to_dict()),
        title=title,
        status=session.state,
        subtitle=(
            f"{route_kind} · {turn_count} "
            f"{'turn' if turn_count == 1 else 'turns'}"
        ),
        # A Meld artifact is target-scoped.  Grouping by its persisted target
        # is therefore stable and does not invent a separate project model.
        group=session.target.context_name,
        modified_timestamp=stat.st_mtime,
        modified_at=modified.isoformat(timespec="seconds"),
        detail=(
            f"Modified {modified.isoformat(timespec='seconds')} from file "
            "metadata.\n"
            f"Session {session.uid}\n"
            f"Target {session.target.context_name} "
            f"[{session.target.context_uid[:8]}]\n"
            f"Mode {session.mode}\n"
            f"State {session.state}\n"
            f"Record {'RETAINED TERMINAL HISTORY' if archived else 'ACTIVE'}"
        ),
        reopen_argv=(
            ("mem", "impact", "meld", "--session", session.uid)
            if archived
            else _reopen_argv(session)
        ),
        archived=archived,
    )


def list_meld_session_catalog(
    store: MemoryStore,
    *,
    target_context_uids: Collection[str] | None = None,
) -> tuple[MeldSessionCatalogEntry, ...]:
    """Return validated saved Meld sessions in recent-file-modification order.

    A scoped artifact reader supplies the exact Context UIDs in its already
    frozen search frame.  Filter by the target-scoped storage key before
    opening session content so an unrelated legacy or damaged session cannot
    make an otherwise independent Find or Query fail.  Session launchers omit
    the filter and retain full-store validation.
    """
    directory = store.meld_sessions_dir
    if not directory.exists():
        return ()
    if directory.is_symlink() or not directory.is_dir():
        raise MeldSessionCatalogError("Meld session storage is invalid.")

    result: list[MeldSessionCatalogEntry] = []
    try:
        candidates = sorted(directory.iterdir(), key=lambda path: path.name)
    except OSError as error:
        raise MeldSessionCatalogError(
            "Meld session storage could not be listed."
        ) from error
    for path in candidates:
        # Atomic-write scratch files are dot-prefixed and are not sessions.
        if path.name.startswith(".") or path.suffix != ".json":
            continue
        if path.is_symlink() or not path.is_file():
            raise MeldSessionCatalogError("Meld session storage is invalid.")
        key = _canonical_storage_key(path)
        if target_context_uids is not None and key not in target_context_uids:
            continue
        try:
            session = store.load_meld_session(key)
        except (OSError, TypeError, ValueError) as error:
            raise MeldSessionCatalogError(
                f"Saved Meld session '{path.name}' is invalid."
            ) from error
        if session is None:
            # A concurrent deletion is not a selection.  It will simply be
            # absent from this read-only snapshot.
            continue
        result.append(
            _catalog_entry(
                path,
                session,
                key=key,
                archived=False,
            )
        )
    try:
        histories = store.list_meld_session_history()
    except (OSError, TypeError, ValueError) as error:
        raise MeldSessionCatalogError("Meld session history is invalid.") from error
    for session, path in histories:
        if (
            target_context_uids is not None
            and session.target.context_uid not in target_context_uids
        ):
            continue
        result.append(
            _catalog_entry(
                path,
                session,
                key=session.uid,
                archived=True,
            )
        )
    return tuple(
        sorted(
            result,
            key=lambda entry: (
                -entry.modified_timestamp,
                entry.group.casefold(),
                entry.title.casefold(),
                entry.key,
            ),
        )
    )


def reload_selected_meld_session(
    store: MemoryStore,
    entry: MeldSessionCatalogEntry,
) -> MeldSession:
    """Reload one picker selection and reject replacement under the same key."""
    try:
        session = (
            store.load_meld_session_history(
                entry.target_context_uid,
                entry.session_uid,
            )
            if entry.archived
            else store.load_meld_session(entry.target_context_uid)
        )
    except (OSError, TypeError, ValueError) as error:
        raise MeldSessionCatalogError(
            "The selected Meld session is no longer valid. Reopen the list."
        ) from error
    if session is None:
        raise MeldSessionCatalogError(
            "The selected Meld session no longer exists. Reopen the list."
        )
    if (
        session.uid != entry.session_uid
        or meld_canonical_digest(session.to_dict()) != entry.session_digest
    ):
        raise MeldSessionCatalogError(
            "The selected Meld session changed while the list was open. "
            "Reopen the list."
        )
    return session
