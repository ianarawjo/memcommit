"""A detached, Profile-bound Markdown watcher using ordinary Sync planning."""

from __future__ import annotations

import fcntl
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from memcommit.application.operations.import_export_sync.mem_sync.automatic.runtime import (
    AutomaticSyncOutcome,
    automatic_owner_matches,
    record_automatic_outcome,
    synchronize_automatically,
)
from memcommit.configuration.workspace import WorkspaceError, workspace_lock
from memcommit.persistence.import_export.source import read_project_documents
from memcommit.persistence.operations.mem_sync.automatic import (
    automatic_sync_lease,
    open_sync_lock,
    read_automatic_record,
    read_automatic_settings,
    sync_operation_lock,
    write_automatic_record,
)
from memcommit.persistence.store import ProfileStore


def worker_is_running(store):
    try:
        fd = open_sync_lock(store, "automatic-worker.lock")
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False
    finally:
        os.close(fd)


def ensure_worker(store):
    """Start one worker for this consent generation, never signal a stored PID."""
    settings = read_automatic_settings(store)
    if not settings.enabled:
        return
    launched = None
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if worker_is_running(store):
            record = read_automatic_record(store, "automatic-worker.json") or {}
            if record.get("generation") == settings.generation:
                return
            # An old generation exits on its next poll; do not mistake it for
            # the new worker after a quick off/on sequence.
        elif launched is None:
            stat = store.store_dir.stat()
            launched = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    __name__,
                    str(store.store_dir),
                    settings.generation,
                    str(stat.st_dev),
                    str(stat.st_ino),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        elif launched.poll() is not None:
            raise RuntimeError(
                "Automatic Sync watcher did not start; run 'mem sync --auto on' to retry."
            )
        time.sleep(0.025)
    raise RuntimeError(
        "Automatic Sync watcher startup timed out; inspect 'mem sync --auto status'."
    )


def sync_input_fingerprint(store):
    """Observe bounded selected documents and native content, excluding receipts."""
    snapshot = read_project_documents(store.store_dir.parent)
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            (snapshot.directories, list(name for name, _ in snapshot.files))
        ).encode()
    )
    digest.update(snapshot.ignore_bytes or b"")
    for name, data in snapshot.files:
        digest.update(name.encode())
        digest.update(hashlib.sha256(data).digest())
    for context in sorted(store.load_all_contexts(), key=lambda value: value.name):
        digest.update(
            json.dumps(context.to_dict(), sort_keys=True, ensure_ascii=False).encode()
        )
    return digest.hexdigest()


def watch_profile(store, generation, stop, *, identity=None, interval=0.5):
    """Wait for two stable observations; the operation lease excludes CLI work."""
    observed = completed = None
    last_error = None
    with ExitStack() as lifecycle:
        with workspace_lock():
            if store.store_dir.is_symlink() or not store.store_dir.is_dir():
                return
            stat = store.store_dir.stat()
            identity = identity or (stat.st_dev, stat.st_ino)
            settings = read_automatic_settings(store)
            if (
                identity != (stat.st_dev, stat.st_ino)
                or not settings.enabled
                or settings.generation != generation
                or not automatic_owner_matches(store, settings)
            ):
                return
            owned = lifecycle.enter_context(
                automatic_sync_lease(store, "automatic-worker.lock", blocking=False)
            )
            if not owned:
                return
            write_automatic_record(
                store,
                "automatic-worker.json",
                {
                    "generation": generation,
                    "pid": os.getpid(),
                },
            )
        while not stop.is_set():
            try:
                stat = store.store_dir.stat()
                if store.store_dir.is_symlink() or identity != (
                    stat.st_dev,
                    stat.st_ino,
                ):
                    return
                with workspace_lock():
                    with sync_operation_lock(store, blocking=False) as acquired:
                        if acquired:
                            settings = read_automatic_settings(store)
                            if (
                                not settings.enabled
                                or settings.generation != generation
                                or not automatic_owner_matches(store, settings)
                            ):
                                return
                            status = (
                                read_automatic_record(store, "automatic-status.json")
                                or {}
                            )
                            if status.get("state") != "paused":
                                fingerprint = sync_input_fingerprint(store)
                                last_error = None
                                if fingerprint == observed and fingerprint != completed:
                                    synchronize_automatically(
                                        store,
                                        trigger="FILE_CHANGE",
                                        generation=generation,
                                    )
                                    # Do not consume a post-publication fingerprint:
                                    # it could include a new editor save not yet applied.
                                    completed = fingerprint
                                observed = fingerprint
            except FileNotFoundError:
                if not store.store_dir.is_dir():
                    return
                observed = completed = None
            except WorkspaceError:
                pass  # A Profile relocation owns the workspace; retry after it ends.
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
                observed = completed = None
                try:
                    # Error reporting writes too. Reacquire the workspace lease
                    # and identity before atomic IO can recreate a relocated root.
                    with workspace_lock():
                        stat = store.store_dir.stat()
                        if store.store_dir.is_symlink() or identity != (
                            stat.st_dev,
                            stat.st_ino,
                        ):
                            return
                        with sync_operation_lock(store):
                            settings = read_automatic_settings(store)
                            if (
                                not settings.enabled
                                or settings.generation != generation
                                or not automatic_owner_matches(store, settings)
                            ):
                                return
                            if str(error) != last_error:
                                record_automatic_outcome(
                                    store,
                                    AutomaticSyncOutcome("error", str(error)),
                                    trigger="FILE_CHANGE",
                                )
                                last_error = str(error)
                except WorkspaceError:
                    pass  # A concurrent relocation can finish before the next poll.
                except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                    return
            stop.wait(interval)


def main():
    root, generation, device, inode = sys.argv[1:]
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda _signal, _frame: stop.set())
    watch_profile(
        ProfileStore(root=Path(root), create=False),
        generation,
        stop,
        identity=(int(device), int(inode)),
    )


if __name__ == "__main__":
    main()
