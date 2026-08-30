"""Immutable terminal Update receipts retained beside the active singleton."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import uuid

from memcommit.application.operations.update.model import UpdateSession


if TYPE_CHECKING:
    from memcommit.persistence.store import MemoryStore


class UpdateReceiptStore:
    """UID-addressed terminal evidence; never a resumable Update work slot."""

    def __init__(self, store: MemoryStore):
        self.store = store
        self.directory = store.store_dir / "update-receipts"

    def path(self, session_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(session_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Update receipt UID is invalid.") from error
        if canonical != session_uid:
            raise ValueError("Update receipt UID is invalid.")
        return self.directory / f"{canonical}.json"

    @staticmethod
    def _same_application_evidence(
        first: UpdateSession,
        second: UpdateSession,
    ) -> bool:
        first_record = first.to_dict()
        second_record = second.to_dict()
        # Undo/Redo changes current command state, not the facts of the
        # original Update application. The first retained terminal projection
        # remains immutable and independently reviewable.
        first_record.pop("status", None)
        second_record.pop("status", None)
        return first_record == second_record

    def save_terminal(self, session: UpdateSession) -> None:
        if session.status not in {"applied", "undone"} or session.application is None:
            raise ValueError("Update receipt storage requires terminal evidence.")
        path = self.path(session.uid)
        existing = self.store._load_update_session(path)
        if existing is not None:
            if not self._same_application_evidence(existing, session):
                raise ValueError(
                    f"Update receipt '{session.uid}' already retains different "
                    "application evidence."
                )
            return
        self.store._save_update_session(path, session)

    def load(self, session_uid: str) -> UpdateSession:
        session = self.store._load_update_session(self.path(session_uid))
        if session is None:
            raise FileNotFoundError(f"Update receipt '{session_uid}' is unavailable.")
        if session.status not in {"applied", "undone"} or session.application is None:
            raise ValueError("Stored Update receipt is not terminal evidence.")
        return session

    def list(self) -> tuple[UpdateSession, ...]:
        if not self.directory.exists():
            return ()
        if self.directory.is_symlink() or not self.directory.is_dir():
            raise ValueError("Update receipt storage is invalid.")
        sessions: list[UpdateSession] = []
        for path in sorted(self.directory.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Update receipt storage contains an invalid entry.")
            uid = path.stem
            if path != self.path(uid):
                raise ValueError("Update receipt storage contains an invalid name.")
            sessions.append(self.load(uid))
        return tuple(
            sorted(
                sessions,
                key=lambda session: (session.application.applied_at, session.uid),
                reverse=True,
            )
        )
