"""Private CAS storage for not-yet-created Ground workspace receipts."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
from typing import Iterator
import uuid

from memcommit.application.operations.ground.workspace_draft import (
    GroundWorkspaceDraft,
    GroundWorkspaceDraftError,
    ground_workspace_draft_digest,
)
from memcommit.persistence.store.infrastructure.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


class GroundWorkspaceDraftStore:
    """Store hidden resume receipts without creating ordinary Contexts."""

    def __init__(self, store: MemoryStore):
        self.store = store
        self.directory = store.store_dir / "ground-workspace-drafts"

    def _path(self, uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise GroundWorkspaceDraftError(
                "Ground draft identity is invalid."
            ) from error
        if canonical != uid:
            raise GroundWorkspaceDraftError("Ground draft identity is invalid.")
        return self.directory / f"{uid}.json"

    def path(self, uid: str) -> Path:
        return self._path(uid)

    def _validate_directory(self, *, create: bool) -> None:
        if self.directory.is_symlink() or (
            self.directory.exists() and not self.directory.is_dir()
        ):
            raise GroundWorkspaceDraftError(
                "Ground draft storage is invalid."
            )
        if create:
            ensure_private_directory(self.store.store_dir, parents=True)
            ensure_private_directory(self.directory)

    @contextmanager
    def _catalog_write_lock(self) -> Iterator[None]:
        self._validate_directory(create=True)
        lock_path = self.directory / ".catalog.lock"
        if lock_path.is_symlink() or (
            lock_path.exists() and not lock_path.is_file()
        ):
            raise GroundWorkspaceDraftError(
                "Ground draft lock storage is invalid."
            )
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def load(self, uid: str) -> GroundWorkspaceDraft:
        self._validate_directory(create=False)
        path = self._path(uid)
        if not path.is_file() or path.is_symlink():
            raise GroundWorkspaceDraftError(
                f"Ground draft '{uid}' was not found."
            )
        try:
            with open(path, encoding="utf-8") as handle:
                value = json.load(handle, object_pairs_hook=_strict_json_object)
            return GroundWorkspaceDraft.from_dict(value)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise GroundWorkspaceDraftError(
                "Saved Ground draft is invalid."
            ) from error

    def list(self) -> tuple[GroundWorkspaceDraft, ...]:
        if not self.directory.exists():
            if self.directory.is_symlink():
                raise GroundWorkspaceDraftError(
                    "Ground draft storage is invalid."
                )
            return ()
        self._validate_directory(create=False)
        drafts: list[GroundWorkspaceDraft] = []
        for path in self.directory.iterdir():
            if path.name == ".catalog.lock" and path.is_file() and not path.is_symlink():
                continue
            if path.name.startswith(".") and ".json.write-" in path.name:
                continue
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise GroundWorkspaceDraftError(
                    "Ground draft storage is invalid."
                )
            draft = self.load(path.stem)
            if draft.uid != path.stem:
                raise GroundWorkspaceDraftError(
                    "Ground draft storage identity is invalid."
                )
            drafts.append(draft)
        return tuple(sorted(drafts, key=lambda item: (item.updated_at, item.uid)))

    def find_by_workspace_name(
        self,
        name: str,
    ) -> GroundWorkspaceDraft | None:
        matches = tuple(
            draft for draft in self.list() if draft.workspace_name == name
        )
        if len(matches) > 1:
            raise GroundWorkspaceDraftError(
                "Multiple Ground drafts use the same Save Location."
            )
        return matches[0] if matches else None

    def save(
        self,
        draft: GroundWorkspaceDraft,
        *,
        expected_digest: str | None,
    ) -> None:
        """Create or CAS-replace one draft while preserving name uniqueness."""

        restored = GroundWorkspaceDraft.from_dict(draft.to_dict())
        path = self._path(restored.uid)
        with self.store.profile_write_guard():
            with self._catalog_write_lock():
                existing_by_name = tuple(
                    item
                    for item in self.list()
                    if item.workspace_name == restored.workspace_name
                    and item.uid != restored.uid
                )
                if existing_by_name:
                    raise ConcurrentContextUpdateError(
                        "A Ground draft already uses this Save Location."
                    )
                if path.exists() and (
                    not path.is_file() or path.is_symlink()
                ):
                    raise GroundWorkspaceDraftError(
                        "Ground draft storage is invalid."
                    )
                if path.exists():
                    current = self.load(restored.uid)
                    if expected_digest is None:
                        raise ConcurrentContextUpdateError(
                            "The Ground draft already exists."
                        )
                    if ground_workspace_draft_digest(current) != expected_digest:
                        raise ConcurrentContextUpdateError(
                            "The Ground draft changed before it could be saved."
                        )
                elif expected_digest is not None:
                    raise ConcurrentContextUpdateError(
                        "The Ground draft no longer exists."
                    )
                self._write(path, restored)

    def delete(self, uid: str, *, expected_digest: str) -> None:
        """Delete only the exact draft consumed by successful creation."""

        with self.store.profile_write_guard():
            with self._catalog_write_lock():
                current = self.load(uid)
                if ground_workspace_draft_digest(current) != expected_digest:
                    raise ConcurrentContextUpdateError(
                        "The Ground draft changed before it could be removed."
                    )
                path = self._path(uid)
                path.unlink()
                _fsync_directory(self.directory)

    def _write(self, path: Path, draft: GroundWorkspaceDraft) -> None:
        temporary = self.directory / f".{path.name}.write-{uuid.uuid4().hex}"
        try:
            descriptor = open_private_exclusive(temporary)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    draft.to_dict(),
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600, follow_symlinks=False)
            _fsync_directory(self.directory)
        finally:
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GroundWorkspaceDraftError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = ["GroundWorkspaceDraftStore"]
