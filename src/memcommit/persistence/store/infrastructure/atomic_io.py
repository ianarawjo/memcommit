"""Atomic persistence primitives shared by Store owners."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Literal, TextIO

from memcommit.core.json_objects import canonical_json_digest
from memcommit.persistence.store.infrastructure.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)


@contextmanager
def _atomic_write_stream(
    path: Path, *, mode: Literal["w", "wb"]
) -> Iterator[TextIO | BinaryIO]:
    """Publish a private staged stream only after its contents are flushed."""
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        ensure_private_directory(path.parent, parents=True)
        descriptor = open_private_exclusive(temporary)
        try:
            # Retain descriptor ownership through partial stream construction;
            # fdopen may otherwise close it before raising its original error.
            with os.fdopen(
                descriptor,
                mode,
                encoding="utf-8" if mode == "w" else None,
                closefd=False,
            ) as stream:
                yield stream
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _write_json_atomic(path: Path, data: object) -> None:
    """Write owner-only JSON through a same-directory atomic replacement."""
    with _atomic_write_stream(path, mode="w") as file:
        json.dump(data, file, indent=2)


def _fsync_directory(path: Path) -> None:
    """Persist a directory-entry change at a multi-file commit boundary."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    """Restore owner-only bytes through the JSON replace boundary."""
    with _atomic_write_stream(path, mode="wb") as file:
        file.write(data)


_canonical_json_digest = canonical_json_digest
