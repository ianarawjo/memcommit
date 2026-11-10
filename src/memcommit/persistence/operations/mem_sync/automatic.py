"""Profile-local automatic Sync consent, status, and cooperative leases."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID, uuid4

from memcommit.core.json_objects import reject_duplicate_json_keys
from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic
from memcommit.persistence.store.infrastructure.storage_permissions import (
    ensure_private_directory,
)

from .run_repository import sync_record_path


@dataclass(frozen=True)
class AutomaticSyncSettings:
    enabled: bool = False
    generation: str | None = None
    profile_uid: str | None = None


def read_automatic_record(store, name):
    path = sync_record_path(store, name)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 16_384:
        raise ValueError("Invalid automatic Sync record.")
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_json_keys
    )
    if not isinstance(value, dict):
        raise ValueError("Invalid automatic Sync record.")
    return value


def read_automatic_settings(store) -> AutomaticSyncSettings:
    value = read_automatic_record(store, "automatic.json")
    if value is None:
        return AutomaticSyncSettings()
    if (
        set(value) != {"version", "enabled", "generation", "profile_uid"}
        or type(value["version"]) is not int
        or value["version"] != 1
        or type(value["enabled"]) is not bool
    ):
        raise ValueError("Invalid automatic Sync settings.")
    for field in ("generation", "profile_uid"):
        identifier = value[field]
        if field == "profile_uid" and identifier is None:
            continue
        if not isinstance(identifier, str) or str(UUID(identifier)) != identifier:
            raise ValueError("Invalid automatic Sync identity.")
    return AutomaticSyncSettings(
        value["enabled"], value["generation"], value["profile_uid"]
    )


def write_automatic_record(store, name, value):
    if store.store_dir.is_symlink() or not store.store_dir.is_dir():
        raise ValueError("Automatic Sync requires an existing ordinary Store.")
    _write_json_atomic(sync_record_path(store, name), value)


def write_automatic_settings(store, enabled: bool, *, profile_uid=None):
    if type(enabled) is not bool:
        raise ValueError("Automatic Sync enabled must be a boolean.")
    settings = AutomaticSyncSettings(enabled, str(uuid4()), profile_uid)
    write_automatic_record(
        store,
        "automatic.json",
        {
            "version": 1,
            "enabled": settings.enabled,
            "generation": settings.generation,
            "profile_uid": settings.profile_uid,
        },
    )
    return settings


def open_sync_lock(store, name, *, create=False):
    """Open only ordinary files; a substituted FIFO must never block startup."""
    path = sync_record_path(store, name)
    if store.store_dir.is_symlink() or not store.store_dir.is_dir():
        raise ValueError("Automatic Sync requires an existing ordinary Store.")
    # A concurrent root relocation must fail here, never recreate the old Store.
    if create:
        ensure_private_directory(path.parent, parents=False)
    flags = (os.O_CREAT | os.O_RDWR) if create else os.O_RDONLY
    fd = os.open(path, flags | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("Automatic Sync lock must be an ordinary file.")
    except BaseException:
        os.close(fd)
        raise
    return fd


@contextmanager
def automatic_sync_lease(store, name, *, blocking=True):
    """Keep raw descriptor ownership; a nonblocking worker can defer a busy cycle."""
    fd = open_sync_lock(store, name, create=True)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
        else:
            yield True
    finally:
        os.close(fd)


_held_sync_roots: ContextVar[frozenset[str]] = ContextVar(
    "held_sync_roots", default=frozenset()
)


@contextmanager
def sync_operation_lock(store, *, blocking=True):
    """Serialize explicit Sync and automatic cycles with their composing command."""
    key = str(store.store_dir.resolve())
    held = _held_sync_roots.get()
    if key in held:
        yield True
        return
    with automatic_sync_lease(store, "operation.lock", blocking=blocking) as acquired:
        if not acquired:
            yield False
            return
        token = _held_sync_roots.set(held | {key})
        try:
            yield True
        finally:
            _held_sync_roots.reset(token)
