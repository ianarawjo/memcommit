"""Operation-owned private CAS persistence for Sever review sessions."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import uuid
from pathlib import Path
from typing import Iterator

from memcommit.application.operations.semantic_updates.curate_integrate.sever.model import SeverError, SeverSession, sever_record_digest
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


class SeverSessionStore:
    def __init__(self, store: MemoryStore):
        self.store = store
        self.directory = store.store_dir / "sever-sessions"

    def _path(self, uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(uid))
        except ValueError as error:
            raise SeverError("Invalid Sever session uid.") from error
        if canonical != uid:
            raise SeverError("Invalid Sever session uid.")
        return self.directory / f"{uid}.json"

    @contextmanager
    def _write_lock(self, uid: str) -> Iterator[None]:
        lock_directory = self.directory / ".locks"
        if lock_directory.exists() and (
            not lock_directory.is_dir() or lock_directory.is_symlink()
        ):
            raise SeverError("Sever session lock storage is invalid.")
        lock_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = lock_directory / f"{uid}.lock"
        if lock_path.exists() and (not lock_path.is_file() or lock_path.is_symlink()):
            raise SeverError("Sever session lock storage is invalid.")
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def save(self, session: SeverSession, *, expected_digest: str | None) -> None:
        path = self._path(session.uid)
        data = session.to_dict()
        with self.store.profile_write_guard():
            if self.directory.exists() and (not self.directory.is_dir() or self.directory.is_symlink()):
                raise SeverError("Sever session storage is invalid.")
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self._write_lock(session.uid):
                if path.exists() and (not path.is_file() or path.is_symlink()):
                    raise SeverError("Sever session storage is invalid.")
                if path.exists():
                    with open(path, encoding="utf-8") as handle:
                        current = json.load(handle)
                    if expected_digest is None:
                        raise ConcurrentContextUpdateError("A Sever session already exists.")
                    if sever_record_digest(current) != expected_digest:
                        raise ConcurrentContextUpdateError(
                            "The Sever session changed before it could be saved."
                        )
                elif expected_digest is not None:
                    raise ConcurrentContextUpdateError("The Sever session no longer exists.")
                temporary = self.directory / f".{path.name}.write-{uuid.uuid4().hex}"
                try:
                    descriptor = os.open(
                        temporary,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                        json.dump(data, handle, indent=2)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, path)
                finally:
                    if temporary.exists() and not temporary.is_symlink():
                        temporary.unlink()

    def load(self, uid: str) -> SeverSession:
        path = self._path(uid)
        if not path.is_file() or path.is_symlink():
            raise SeverError(f"Sever session '{uid}' not found.")
        try:
            with open(path, encoding="utf-8") as handle:
                return SeverSession.from_dict(json.load(handle))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SeverError("Saved Sever session is invalid.") from error

    def list(self) -> tuple[SeverSession, ...]:
        if not self.directory.exists():
            return ()
        if not self.directory.is_dir() or self.directory.is_symlink():
            raise SeverError("Sever session storage is invalid.")
        sessions = [self.load(path.stem) for path in self.directory.glob("*.json")]
        return tuple(sorted(sessions, key=lambda item: item.uid))
