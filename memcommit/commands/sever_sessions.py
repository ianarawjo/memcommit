"""Read-only catalog adapter for saved Sever review sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from memcommit.interfaces.tui.components.operation_launcher.session import SessionPickerEntry
from memcommit.operations.sever.model import SeverSession, sever_record_digest
from memcommit.operations.sever.session_store import SeverSessionStore


_ATOMIC_TEMP_NAME = re.compile(
    r"^\.[0-9a-f-]{36}\.json\.write-[0-9a-f]{32}$"
)


@dataclass(frozen=True)
class SeverSessionCatalogEntry:
    """One picker row plus immutable evidence for safe reopening."""

    picker_entry: SessionPickerEntry
    session_digest: str


def _scope_label(session: SeverSession, *, source: bool) -> str:
    binding = session.source if source else session.criteria
    return "SUBTREE" if binding.include_descendants else "THIS CONTEXT ONLY"


def list_sever_session_catalog(
    sessions: SeverSessionStore,
) -> tuple[SeverSessionCatalogEntry, ...]:
    """Project every validated Sever record into the common session picker."""

    directory = sessions.directory
    if not directory.exists():
        if directory.is_symlink():
            raise ValueError("Sever session storage is invalid.")
        return ()
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Sever session storage is invalid.")

    result: list[SeverSessionCatalogEntry] = []
    for path in sorted(directory.iterdir(), key=lambda candidate: candidate.name):
        if path.name == ".locks" and path.is_dir() and not path.is_symlink():
            continue
        if _ATOMIC_TEMP_NAME.fullmatch(path.name) is not None:
            continue
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            raise ValueError("Sever session storage is invalid.")
        session = sessions.load(path.stem)
        if session.uid != path.stem:
            raise ValueError(
                "Saved Sever session does not match its storage identity."
            )
        modified_at = path.stat().st_mtime
        modified = datetime.fromtimestamp(
            modified_at,
            tz=timezone.utc,
        ).isoformat(timespec="seconds")
        picker_entry = SessionPickerEntry(
            kind="sever",
            key=session.uid,
            title=(
                f"{session.source.root_name} × {session.criteria.root_name} "
                f"→ {session.output_name}"
            ),
            status=(
                f"{session.state} · "
                + (
                    "SELF-SAVE"
                    if session.save_mode == "SELF_SAVE"
                    else "OTHER-SAVE"
                )
            ),
            subtitle=(
                f"{len(session.candidates)} result "
                f"{'decision' if len(session.candidates) == 1 else 'decisions'}"
            ),
            group=session.source.root_name,
            sort_timestamp=modified_at,
            detail="\n".join(
                (
                    f"Last saved: {modified}",
                    f"Source: {session.source.root_name} "
                    f"({_scope_label(session, source=True)})",
                    f"Criteria: {session.criteria.root_name} "
                    f"({_scope_label(session, source=False)})",
                    f"Output: {session.output_name} · "
                    + (
                        "SOURCE UPDATED"
                        if session.save_mode == "SELF_SAVE"
                        and session.state == "APPLIED"
                        else "WILL UPDATE SOURCE"
                        if session.save_mode == "SELF_SAVE"
                        else "CREATED LOCALLY"
                        if session.state == "APPLIED"
                        else "CREATE ON APPLY"
                    ),
                    (
                        "Source: SELF-SAVE TARGET"
                        if session.save_mode == "SELF_SAVE"
                        else "Source: UNCHANGED"
                    ),
                )
            ),
            reopen_argv=("mem", "sever", "--resume", session.uid),
        )
        result.append(
            SeverSessionCatalogEntry(
                picker_entry=picker_entry,
                session_digest=sever_record_digest(session),
            )
        )
    return tuple(
        sorted(
            result,
            key=lambda entry: (
                -entry.picker_entry.sort_timestamp,
                entry.picker_entry.title.casefold(),
                entry.picker_entry.key,
            ),
        )
    )


def reload_selected_sever_session(
    sessions: SeverSessionStore,
    entry: SeverSessionCatalogEntry,
) -> SeverSession:
    """Reload a picker selection and reject deletion or in-place replacement."""

    try:
        session = sessions.load(entry.picker_entry.key)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(
            "The selected Sever session is no longer available. Reopen the list."
        ) from error
    if (
        session.uid != entry.picker_entry.key
        or sever_record_digest(session) != entry.session_digest
    ):
        raise ValueError(
            "The selected Sever session changed while the list was open. "
            "Reopen the list."
        )
    return session
