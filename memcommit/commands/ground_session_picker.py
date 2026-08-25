"""Read-only presentation adapter for saved named Ground sessions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

import memcommit.store as store_module
from memcommit.interfaces.tui.components.operation_launcher.location import (
    operation_launcher_orientation,
)
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionPickerEntry,
    SessionPickerLocation,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.ground import GroundSession, validate_ground_contract_name
from memcommit.store import (
    MemoryStore,
    ground_session_record_digest,
)


_ATOMIC_TEMP_NAME = re.compile(r"^\..+\.json\.write-[0-9a-f]{32}$")


@dataclass(frozen=True)
class GroundSessionCatalogEntry:
    """One picker projection plus immutable evidence for safe reopening."""

    picker_entry: SessionPickerEntry
    session_uid: str
    session_revision: int
    session_digest: str


def session_picker_location(
    store: MemoryStore | None = None,
) -> SessionPickerLocation:
    """Compatibility projection for saved-session launcher callers."""

    orientation = operation_launcher_orientation(store)
    rows = dict(orientation.rows)
    return SessionPickerLocation(
        profile_name=rows["PROFILE"],
        store_path=rows["STORE"],
    )


def ground_session_picker_location() -> SessionPickerLocation:
    """Compatibility name for Ground's use of the shared orientation."""

    return session_picker_location()


def _ground_primary_context(session: GroundSession) -> str:
    """Return a display grouping without inventing a durable project ID."""
    for preferred_role in ("RAW_EVIDENCE", "WORKING_CANDIDATES"):
        for frame in session.frames:
            if frame.role == preferred_role:
                return frame.context_name
    return "Unbound"


def _ground_detail(session: GroundSession, *, modified_at: float) -> str:
    contexts = tuple(frame.context_name for frame in session.frames)
    rules = sum(item.kind == "RULE" for item in session.items)
    memories = sum(item.kind == "CASE" for item in session.items)
    decisions = sum(item.kind == "DECISION" for item in session.items)
    modified = datetime.fromtimestamp(modified_at).astimezone().isoformat(
        timespec="seconds"
    )
    return "\n".join(
        (
            f"Goal: {display_escape_text(session.goal or '(not yet stated)')}",
            (
                "Contexts: "
                + display_escape_text(", ".join(contexts))
                if contexts
                else "Contexts: Unbound"
            ),
            f"Rules: {rules} · Memories: {memories} · Decisions: {decisions}",
            f"Last saved: {modified}",
        )
    )


def list_ground_session_catalog(
    store: MemoryStore,
) -> tuple[GroundSessionCatalogEntry, ...]:
    """Return validated read-only Ground summaries for the shared picker.

    Filesystem modification time is deliberately presentation metadata, not
    Ground identity or CAS state. It is labelled "last saved" because merely
    opening a Ground does not update it and copying a store may rewrite it.
    """
    root = store_module.GROUND_SESSIONS_DIR
    if not root.exists():
        if root.is_symlink():
            raise ValueError("Grounding session storage is invalid.")
        return ()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Grounding session storage is invalid.")

    entries: list[GroundSessionCatalogEntry] = []
    for path in sorted(root.iterdir(), key=lambda candidate: candidate.name):
        if path.name == ".locks" and path.is_dir() and not path.is_symlink():
            continue
        if _ATOMIC_TEMP_NAME.fullmatch(path.name) is not None:
            # Atomic-write scratch files have not become durable Grounds yet.
            continue
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            raise ValueError("Grounding session storage is invalid.")
        contract_name = validate_ground_contract_name(path.stem)
        session = store.load_ground_session(contract_name)
        if session is None:
            raise ValueError("Saved Ground disappeared while being listed.")
        modified_at = path.stat().st_mtime
        picker_entry = SessionPickerEntry(
                kind="ground",
                key=session.contract_name,
                title=session.contract_name,
                status=f"{session.status} · rev {session.revision}",
                subtitle=session.goal or "(goal not yet stated)",
                group=_ground_primary_context(session),
                sort_timestamp=modified_at,
                detail=_ground_detail(session, modified_at=modified_at),
                reopen_argv=("mem", "ground", session.contract_name),
        )
        entries.append(
            GroundSessionCatalogEntry(
                picker_entry=picker_entry,
                session_uid=session.uid,
                session_revision=session.revision,
                session_digest=ground_session_record_digest(session),
            )
        )
    return tuple(entries)


def list_ground_session_entries(
    store: MemoryStore,
) -> tuple[SessionPickerEntry, ...]:
    """Return the presentation-only projection for compatibility callers."""
    return tuple(
        entry.picker_entry for entry in list_ground_session_catalog(store)
    )


def reload_selected_ground_session(
    store: MemoryStore,
    entry: GroundSessionCatalogEntry,
) -> GroundSession:
    """Reload a selected Ground and reject deletion or in-place replacement."""
    session = store.load_ground_session(entry.picker_entry.key)
    if session is None:
        raise ValueError(
            f"Selected Ground '{entry.picker_entry.key}' no longer exists; "
            "nothing was created."
        )
    if (
        session.uid != entry.session_uid
        or session.revision != entry.session_revision
        or ground_session_record_digest(session) != entry.session_digest
    ):
        raise ValueError(
            f"Selected Ground '{entry.picker_entry.key}' changed while the "
            "list was open; reopen the list."
        )
    return session
