"""CAS-write prepared companion records under their existing session locks."""

import json
from pathlib import Path

from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)


def write_companion_session_restore(
    store,
    path: Path,
    *,
    expected: dict[str, object],
    value: dict[str, object],
    sever_sessions,
) -> None:
    """CAS-write one companion session inside command restoration."""
    if sever_sessions is not None and path.parent == sever_sessions.directory:
        uid = path.stem
        if path != sever_sessions._path(uid):
            raise ConcurrentContextUpdateError(
                "The Sever session restore path is invalid."
            )
        with store.profile_write_guard():
            with sever_sessions._write_lock(uid):
                if not path.is_file() or path.is_symlink():
                    raise ConcurrentContextUpdateError(
                        "The applied Sever session changed during restoration."
                    )
                with open(path, encoding="utf-8") as file:
                    current = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                if current != expected:
                    raise ConcurrentContextUpdateError(
                        "The applied Sever session changed during restoration."
                    )
                _write_json_atomic(path, value)
        return
    with store.profile_write_guard():
        if not path.is_file() or path.is_symlink():
            raise ConcurrentContextUpdateError(
                "The companion operation session changed during restoration."
            )
        with open(path, encoding="utf-8") as file:
            current = json.load(
                file,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        if current != expected:
            raise ConcurrentContextUpdateError(
                "The companion operation session changed during restoration."
            )
        _write_json_atomic(path, value)
