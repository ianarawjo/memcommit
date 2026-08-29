"""Provide cooperative Store transaction and session locks."""

from __future__ import annotations
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import os
import uuid
from typing import Iterable, Iterator


from ..context_memory.records import _context_name_parts


class _StoreLockingMixin:
    """Focused slice of the temporary Store assembly."""

    @contextmanager
    def _context_graph_lock(self, *, exclusive: bool) -> Iterator[None]:
        """Coordinate graph-wide Context migrations with ordinary writers.

        Per-name locks cannot protect an inbound-reference scan: another
        process could add a new owner under a previously unseen name while a
        namespace migration is being prepared. Ordinary Context/state writers
        therefore take this lock shared, while rename holds it exclusively
        from its final scan through publication and rollback.
        """
        lock_path = self.store_dir / "context-graph.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Context graph lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
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

    @contextmanager
    def _context_write_lock(self, name: str) -> Iterator[None]:
        """Serialize cooperative Context saves across local mem processes."""
        _context_name_parts(name)
        lock_dir = self.store_dir / "context-write-locks"
        if lock_dir.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Context lock directory.")
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / (
            hashlib.sha256(name.encode("utf-8")).hexdigest() + ".lock"
        )
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            # os.fdopen owns the descriptor once it succeeds. If it fails
            # before taking ownership, close the raw descriptor here.
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

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
    def _command_write_lock(self) -> Iterator[None]:
        """Serialize checkpoint-producing commands across Contexts.

        Per-Context locks prevent lost writes but cannot order two commands
        aimed at different Contexts. Undo/Redo reconstruct one global command
        stack, so future command commits share this short store-wide boundary.
        """
        lock_path = self.store_dir / "context-command-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link command lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
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

    @contextmanager
    def _state_write_lock(self) -> Iterator[None]:
        """Serialize cooperative changes to the global current Context."""
        lock_path = self.store_dir / "state-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link state lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
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

    @contextmanager
    def _update_session_write_lock(self) -> Iterator[None]:
        """Serialize promotion and application of the one active update."""
        lock_path = self.store_dir / "update-session-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link update lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
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
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
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

    @contextmanager
    def _meld_resolution_branch_write_lock(self) -> Iterator[None]:
        """Serialize first-writer-wins publication for exact Meld branches."""
        lock_path = self.store_dir / "meld-resolution-branch-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Meld branch lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
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
