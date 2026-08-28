"""Atomic persistence primitives shared by Store owners."""

from __future__ import annotations
import hashlib
import json
import os
import uuid
from pathlib import Path
from memcommit.application.capabilities.authority.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Build a JSON object while rejecting duplicate keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _write_json_atomic(path: Path, data: object) -> None:
    """Write owner-only JSON through a same-directory atomic replacement."""
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        ensure_private_directory(path.parent, parents=True)
        descriptor = open_private_exclusive(temporary)
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _fsync_directory(path: Path) -> None:
    """Persist a directory-entry change at a multi-file commit boundary."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    """Restore owner-only bytes through the JSON replace boundary."""
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        ensure_private_directory(path.parent, parents=True)
        descriptor = open_private_exclusive(temporary)
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _canonical_json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
