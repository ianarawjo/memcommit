"""Private CAS persistence for completed Memory quality Audit sessions."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import uuid
from pathlib import Path
from typing import Iterator

from memcommit.quality_audit import (
    QualityAuditError,
    QualityAuditSession,
    quality_audit_record_digest,
)
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


class QualityAuditStore:
    """Store every completed Audit by UID without a mutable latest slot."""

    def __init__(self, store: MemoryStore):
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

    def path(self, uid: str) -> Path:
        """Return the validated exact record path for presentation metadata."""

        return self._path(uid)

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
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def save(
        self,
        session: QualityAuditSession,
        *,
        expected_digest: str | None,
    ) -> None:
        """Create or CAS-update one response ledger without replacing its snapshot."""

        restored = QualityAuditSession.from_dict(session.to_dict())
        path = self._path(restored.uid)
        data = restored.to_dict()
        with self.store.profile_write_guard():
            if self.directory.exists() and (
                not self.directory.is_dir() or self.directory.is_symlink()
            ):
                raise QualityAuditError("Audit session storage is invalid.")
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self._write_lock(restored.uid):
                if path.exists() and (not path.is_file() or path.is_symlink()):
                    raise QualityAuditError("Audit session storage is invalid.")
                if path.exists():
                    try:
                        with open(path, encoding="utf-8") as handle:
                            current = QualityAuditSession.from_dict(
                                json.load(handle, object_pairs_hook=_strict_json_object)
                            )
                    except (OSError, ValueError, json.JSONDecodeError) as error:
                        raise QualityAuditError(
                            "Saved Audit session is invalid."
                        ) from error
                    if expected_digest is None:
                        raise ConcurrentContextUpdateError(
                            "An Audit session with this uid already exists."
                        )
                    if quality_audit_record_digest(current) != expected_digest:
                        raise ConcurrentContextUpdateError(
                            "The Audit review changed before it could be saved."
                        )
                    # Responses may change, but a review save can never replace
                    # the provider result it claims to annotate.
                    if current.snapshot_digest != restored.snapshot_digest:
                        raise ConcurrentContextUpdateError(
                            "The immutable Audit snapshot cannot be replaced."
                        )
                elif expected_digest is not None:
                    raise ConcurrentContextUpdateError(
                        "The Audit session no longer exists."
                    )
                temporary = self.directory / f".{path.name}.write-{uuid.uuid4().hex}"
                try:
                    descriptor = os.open(
                        temporary,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                        json.dump(data, handle, indent=2, ensure_ascii=False)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, path)
                finally:
                    if temporary.exists() and not temporary.is_symlink():
                        temporary.unlink()

    def load(self, uid: str) -> QualityAuditSession:
        path = self._path(uid)
        if not path.is_file() or path.is_symlink():
            raise QualityAuditError(f"Audit session '{uid}' not found.")
        try:
            with open(path, encoding="utf-8") as handle:
                return QualityAuditSession.from_dict(
                    json.load(handle, object_pairs_hook=_strict_json_object)
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


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result
