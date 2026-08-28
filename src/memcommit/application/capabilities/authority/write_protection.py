"""Profile-scoped persistent write-protection registry.

Context records deliberately do not carry their own protection bit.  Keeping
the registry beside them lets an unlock remain possible without rewriting the
very Context that is protected, and gives every writer one common policy
snapshot to check at its final persistence boundary.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator
import uuid


WRITE_PROTECTION_SCHEMA_VERSION = 2


class WriteProtectionRegistryError(ValueError):
    """The durable write-protection registry is unsafe or invalid."""


class WriteProtectionError(RuntimeError):
    """A requested durable mutation would cross a protection policy."""


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise WriteProtectionRegistryError(
                f"Duplicate write-protection JSON key: {key}"
            )
        result[key] = value
    return result


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise WriteProtectionRegistryError(f"{label} must be a nonempty string.")
    return value


@dataclass(frozen=True)
class WriteProtectionState:
    """Stable identity keys protected inside one Profile store."""

    profile_protected: bool = False
    context_uids: frozenset[str] = frozenset()
    memory_keys: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def from_dict(cls, value: object) -> "WriteProtectionState":
        if not isinstance(value, dict):
            raise WriteProtectionRegistryError(
                "Write-protection storage must contain an object."
            )
        version = value.get("schema_version")
        if type(version) is not int or version not in {1, 2}:
            raise WriteProtectionRegistryError(
                "Unsupported write-protection schema version."
            )
        expected_keys = {"schema_version", "contexts", "memories"}
        if version == 2:
            expected_keys.add("profile_protected")
        if set(value) != expected_keys:
            raise WriteProtectionRegistryError(
                "Write-protection storage has unexpected fields."
            )
        profile_protected = value.get("profile_protected", False)
        if type(profile_protected) is not bool:
            raise WriteProtectionRegistryError(
                "Write-protection Profile state must be true or false."
            )

        raw_contexts = value["contexts"]
        raw_memories = value["memories"]
        if not isinstance(raw_contexts, list):
            raise WriteProtectionRegistryError(
                "Write-protection contexts must be a list."
            )
        if not isinstance(raw_memories, list):
            raise WriteProtectionRegistryError(
                "Write-protection memories must be a list."
            )

        context_uids = frozenset(
            _identifier(item, "Protected Context uid")
            for item in raw_contexts
        )
        if len(context_uids) != len(raw_contexts):
            raise WriteProtectionRegistryError(
                "A Context is protected more than once."
            )

        memory_keys: list[tuple[str, str]] = []
        for item in raw_memories:
            if not isinstance(item, dict) or set(item) != {
                "context_uid",
                "memory_uid",
            }:
                raise WriteProtectionRegistryError(
                    "A protected Memory entry is invalid."
                )
            memory_keys.append(
                (
                    _identifier(
                        item["context_uid"],
                        "Protected Memory Context uid",
                    ),
                    _identifier(item["memory_uid"], "Protected Memory uid"),
                )
            )
        frozen_memory_keys = frozenset(memory_keys)
        if len(frozen_memory_keys) != len(memory_keys):
            raise WriteProtectionRegistryError(
                "A Memory is protected more than once."
            )
        return cls(
            profile_protected=profile_protected,
            context_uids=context_uids,
            memory_keys=frozen_memory_keys,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": WRITE_PROTECTION_SCHEMA_VERSION,
            "profile_protected": self.profile_protected,
            "contexts": sorted(self.context_uids),
            "memories": [
                {"context_uid": context_uid, "memory_uid": memory_uid}
                for context_uid, memory_uid in sorted(self.memory_keys)
            ],
        }

    @property
    def is_empty(self) -> bool:
        return (
            not self.profile_protected
            and not self.context_uids
            and not self.memory_keys
        )

    def profile_is_protected(self) -> bool:
        return self.profile_protected

    def context_is_protected(self, context_uid: str) -> bool:
        return context_uid in self.context_uids

    def protected_memory_uids(self, context_uid: str) -> frozenset[str]:
        return frozenset(
            memory_uid
            for owner_uid, memory_uid in self.memory_keys
            if owner_uid == context_uid
        )

    def with_context(
        self,
        context_uid: str,
        *,
        protected: bool,
    ) -> "WriteProtectionState":
        next_uids = set(self.context_uids)
        if protected:
            next_uids.add(context_uid)
        else:
            next_uids.discard(context_uid)
        return WriteProtectionState(
            profile_protected=self.profile_protected,
            context_uids=frozenset(next_uids),
            memory_keys=self.memory_keys,
        )

    def with_contexts(
        self,
        context_uids: Iterable[str],
        *,
        protected: bool,
    ) -> "WriteProtectionState":
        next_uids = set(self.context_uids)
        if protected:
            next_uids.update(context_uids)
        else:
            next_uids.difference_update(context_uids)
        return WriteProtectionState(
            profile_protected=self.profile_protected,
            context_uids=frozenset(next_uids),
            memory_keys=self.memory_keys,
        )

    def with_memory(
        self,
        context_uid: str,
        memory_uid: str,
        *,
        protected: bool,
    ) -> "WriteProtectionState":
        next_keys = set(self.memory_keys)
        key = (context_uid, memory_uid)
        if protected:
            next_keys.add(key)
        else:
            next_keys.discard(key)
        return WriteProtectionState(
            profile_protected=self.profile_protected,
            context_uids=self.context_uids,
            memory_keys=frozenset(next_keys),
        )

    def with_profile(self, *, protected: bool) -> "WriteProtectionState":
        return WriteProtectionState(
            profile_protected=protected,
            context_uids=self.context_uids,
            memory_keys=self.memory_keys,
        )


class WriteProtectionRegistry:
    """Serialize and atomically publish one Profile's protection state."""

    def __init__(self, store_root: Path):
        self.store_root = Path(store_root)
        self.path = self.store_root / "write-protection.json"
        # Reuse the transient Context-lock directory so portable store exports
        # already know to omit this process-coordination artifact.
        self.lock_dir = self.store_root / "context-write-locks"
        self.lock_path = self.lock_dir / "write-protection-registry.lock"

    @contextmanager
    def _lock(self, *, exclusive: bool) -> Iterator[None]:
        if self.lock_dir.is_symlink():
            raise WriteProtectionRegistryError(
                "Write-protection lock storage cannot be a symbolic link."
            )
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        if not self.lock_dir.is_dir():
            raise WriteProtectionRegistryError(
                "Write-protection lock storage is invalid."
            )
        if self.lock_path.is_symlink():
            raise WriteProtectionRegistryError(
                "Write-protection lock cannot be a symbolic link."
            )
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
                )
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    def _read_locked(self) -> WriteProtectionState:
        if self.path.is_symlink():
            raise WriteProtectionRegistryError(
                "Write-protection storage cannot be a symbolic link."
            )
        if not self.path.exists():
            return WriteProtectionState()
        if not self.path.is_file():
            raise WriteProtectionRegistryError(
                "Write-protection storage is invalid."
            )
        try:
            with open(self.path, encoding="utf-8") as file:
                value = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
        except json.JSONDecodeError as error:
            raise WriteProtectionRegistryError(
                "Write-protection storage is invalid JSON."
            ) from error
        return WriteProtectionState.from_dict(value)

    def snapshot(self) -> WriteProtectionState:
        with self._lock(exclusive=False):
            return self._read_locked()

    @contextmanager
    def profile_write_guard(self) -> Iterator[WriteProtectionState]:
        """Keep Profile policy stable across one durable store write.

        Profile lock/unlock takes the same registry lock exclusively. Holding
        it shared from the final policy check through publication prevents a
        writer validated under the old policy from landing after ``lock
        profile`` has returned.
        """
        with self._lock(exclusive=False):
            state = self._read_locked()
            if state.profile_is_protected():
                raise WriteProtectionError(
                    "Profile is locked against writes. Unlock that Profile "
                    "first."
                )
            yield state

    def update(
        self,
        transform: Callable[[WriteProtectionState], WriteProtectionState],
    ) -> tuple[WriteProtectionState, WriteProtectionState]:
        with self._lock(exclusive=True):
            before = self._read_locked()
            after = transform(before)
            if not isinstance(after, WriteProtectionState):
                raise TypeError(
                    "Write-protection update must return WriteProtectionState."
                )
            if after == before:
                return before, after
            self._write_locked(after)
            return before, after

    def _write_locked(self, state: WriteProtectionState) -> None:
        if self.path.is_symlink():
            raise WriteProtectionRegistryError(
                "Write-protection storage cannot be a symbolic link."
            )
        if state.is_empty:
            if self.path.exists():
                if not self.path.is_file():
                    raise WriteProtectionRegistryError(
                        "Write-protection storage is invalid."
                    )
                self.path.unlink()
                self._fsync_store_root()
            return

        temporary = self.store_root / (
            f".{self.path.name}.write-{uuid.uuid4().hex}"
        )
        try:
            with open(temporary, "x", encoding="utf-8") as file:
                json.dump(state.to_dict(), file, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
            self._fsync_store_root()
        finally:
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()

    def _fsync_store_root(self) -> None:
        descriptor = os.open(self.store_root, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
