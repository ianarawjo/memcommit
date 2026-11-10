"""Provide cooperative Store transaction and session locks."""

from __future__ import annotations

import fcntl
import hashlib
import os
import uuid
from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from memcommit.core.context_name_validation import validate_context_name


@contextmanager
def _blocking_file_lock(path: Path, *, exclusive: bool) -> Iterator[None]:
    """Hold a cooperative lock; callers own path validation and lock scope."""
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        # Keep one descriptor owner even if fdopen constructs part of a stream
        # before failing. A second close could target a number another thread reused.
        with os.fdopen(
            descriptor, "a+", encoding="utf-8", closefd=False
        ) as lock_file:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
            )
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


class _StoreLockingMixin:
    """Focused slice of the temporary Store assembly."""

    @contextmanager
    def _context_graph_lock(self, *, exclusive: bool) -> Iterator[None]:
        """Coordinate graph-wide Context migrations with ordinary writers.

        Per-name locks cannot freeze namespace membership. Ordinary name/state
        writers take this lock shared; rename holds it exclusively from its
        final namespace scan through publication and rollback.
        """
        lock_path = self.store_dir / "context-graph.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Context graph lock.")
        with _blocking_file_lock(lock_path, exclusive=exclusive):
            yield

    @contextmanager
    def _context_write_lock(self, name: str) -> Iterator[None]:
        """Serialize cooperative Context saves across local mem processes."""
        validate_context_name(name)
        lock_dir = self.store_dir / "context-write-locks"
        if lock_dir.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Context lock directory.")
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / (
            hashlib.sha256(name.encode("utf-8")).hexdigest() + ".lock"
        )
        with _blocking_file_lock(lock_path, exclusive=True):
            yield

    @contextmanager
    def _context_write_locks(
        self,
        names: Iterable[str],
    ) -> Iterator[None]:
        """Hold several Context locks in one deterministic deadlock-free order."""
        ordered = sorted(set(names))
        with ExitStack() as stack:
            for name in ordered:
                stack.enter_context(self._context_write_lock(name))
            yield

    @contextmanager
    def _state_write_lock(self) -> Iterator[None]:
        """Serialize cooperative changes to the global current Context."""
        lock_path = self.store_dir / "state-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link state lock.")
        with _blocking_file_lock(lock_path, exclusive=True):
            yield

    @contextmanager
    def _atomize_session_write_lock(
        self,
        context_uid: str,
    ) -> Iterator[None]:
        """Serialize one Context's analysis/workbench CAS lifecycle."""

        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid Atomize session Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid Atomize session Context uid.")
        lock_dir = self.store_dir / "atomize-session-write-locks"
        if lock_dir.is_symlink():
            raise ValueError("Refusing to use an Atomize session lock symlink.")
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / f"{canonical}.lock"
        with _blocking_file_lock(lock_path, exclusive=True):
            yield
