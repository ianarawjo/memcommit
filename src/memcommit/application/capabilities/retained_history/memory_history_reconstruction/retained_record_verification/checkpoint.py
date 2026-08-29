"""Read and normalize retained checkpoint catalogs."""

from __future__ import annotations

from typing import Any

from memcommit.application.capabilities.retained_history.reconstruction import (
    HistoryError,
    flatten_checkpoint_entries,
)
from memcommit.persistence.store import MemoryStore

from .model import MemoryHistoryReconstructionError


def _checkpoint_entries(store: MemoryStore, context_name: str) -> list[dict]:
    """Return the common current and revert-retained checkpoint catalog."""
    try:
        entries, _physical_uids = flatten_checkpoint_entries(
            store.list_checkpoints(context_name)
        )
    except HistoryError as error:
        raise MemoryHistoryReconstructionError(str(error)) from error
    return entries


def _checkpoint_fields(entry: dict) -> tuple[str, str, str, str, dict[str, Any]]:
    uid = entry["uid"]
    timestamp = entry["timestamp"]
    command = entry.get("command")
    description = entry.get("description") or entry.get("message") or ""
    args = entry.get("args")
    return (
        uid,
        timestamp,
        command if isinstance(command, str) and command else "checkpoint",
        description if isinstance(description, str) else "",
        args if isinstance(args, dict) else {},
    )
