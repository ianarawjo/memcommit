"""JSON persistence adapter for immutable completed Audit records."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from memcommit.application.operations.audit.model import (
    QualityAuditError,
    QualityAuditSession,
)
from memcommit.core.json_objects import reject_duplicate_json_keys
from memcommit.persistence.store import ProfileStore
from memcommit.persistence.store.infrastructure.atomic_io import _atomic_write_stream
from memcommit.persistence.store.infrastructure.locking import _blocking_file_lock


class JsonAuditRecordRepository:
    """Store every completed Audit as one private UID-addressed JSON record."""

    def __init__(self, store: ProfileStore):
        self.store = store
        self.directory = store.store_dir / "quality-audits"

    def _path(self, uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise QualityAuditError("Invalid Audit session uid.") from error
        if canonical != uid:
            raise QualityAuditError("Invalid Audit session uid.")
        return self.directory / f"{uid}.json"

    def modified_at(self, uid: str) -> float | None:
        """Return one validated record's modification time when it exists."""

        path = self._path(uid)
        try:
            if path.is_file() and not path.is_symlink():
                return path.stat().st_mtime
        except FileNotFoundError:
            pass
        return None

    @contextmanager
    def _write_lock(self, uid: str) -> Iterator[None]:
        lock_directory = self.directory / ".locks"
        if lock_directory.exists() and (
            not lock_directory.is_dir() or lock_directory.is_symlink()
        ):
            raise QualityAuditError("Audit session lock storage is invalid.")
        lock_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = lock_directory / f"{uid}.lock"
        if lock_path.exists() and (not lock_path.is_file() or lock_path.is_symlink()):
            raise QualityAuditError("Audit session lock storage is invalid.")
        with _blocking_file_lock(lock_path, exclusive=True):
            yield

    def create(self, session: QualityAuditSession) -> None:
        """Create one immutable UID-addressed Audit record."""

        path = self._path(session.uid)
        data = session.to_dict()
        if self.directory.exists() and (
            not self.directory.is_dir() or self.directory.is_symlink()
        ):
            raise QualityAuditError("Audit session storage is invalid.")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._write_lock(session.uid):
            if path.exists() and (not path.is_file() or path.is_symlink()):
                raise QualityAuditError("Audit session storage is invalid.")
            if path.exists():
                raise QualityAuditError("An Audit record with this uid already exists.")
            with _atomic_write_stream(path, mode="w") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)

    def load(self, uid: str) -> QualityAuditSession:
        path = self._path(uid)
        if not path.is_file() or path.is_symlink():
            raise QualityAuditError(f"Audit session '{uid}' not found.")
        try:
            with open(path, encoding="utf-8") as handle:
                return QualityAuditSession.from_dict(
                    json.load(handle, object_pairs_hook=reject_duplicate_json_keys)
                )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise QualityAuditError("Saved Audit session is invalid.") from error

    def list(self) -> tuple[QualityAuditSession, ...]:
        if not self.directory.exists():
            if self.directory.is_symlink():
                raise QualityAuditError("Audit session storage is invalid.")
            return ()
        if not self.directory.is_dir() or self.directory.is_symlink():
            raise QualityAuditError("Audit session storage is invalid.")
        sessions: list[QualityAuditSession] = []
        for path in self.directory.iterdir():
            if path.name == ".locks" and path.is_dir() and not path.is_symlink():
                continue
            if path.name.startswith(".") and ".json.write-" in path.name:
                continue
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise QualityAuditError("Audit session storage is invalid.")
            sessions.append(self.load(path.stem))
        return tuple(sorted(sessions, key=lambda item: item.uid))
