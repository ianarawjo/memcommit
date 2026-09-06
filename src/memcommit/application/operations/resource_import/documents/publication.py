"""Publish native Context data through the ordinary require-new transaction."""

from __future__ import annotations

from collections.abc import Iterable

from memcommit.application.operations.resource_import.context_data import (
    _closed_import_contexts,
    _reject_context_identity_collisions,
)
from memcommit.core.context import AutoCheckpoint, Context
from memcommit.persistence.store import MemoryStore

from .codec import decode_context


def import_context_records(
    destination: MemoryStore,
    entries: Iterable[tuple[Context, AutoCheckpoint | None]],
    *,
    make_current: str | None = None,
) -> tuple[Context, ...]:
    """Import a complete native set for CLI file input or Study composition.

    Callers own their receipt and run setup. JSON shape, closed references,
    identity collisions and all-new publication have one shared boundary.
    """
    entries = tuple(entries)
    contexts = tuple(decode_context(context.to_dict()) for context, _ in entries)
    names = [context.name for context in contexts]
    uids = [context.uid for context in contexts]
    if len(names) != len(set(names)) or len(uids) != len(set(uids)):
        raise ValueError("Native Context import repeats a Context name or identity.")
    imported = _closed_import_contexts(contexts, {name: name for name in names})
    # The command lock freezes destination writes across the UID scan and
    # creation. Use the locked persistence entry point to avoid re-locking it.
    with destination._command_write_lock():
        _reject_context_identity_collisions(destination, imported)
        return destination._create_missing_contexts_command_locked(
            tuple(
                (context, entry[1])
                for context, entry in zip(imported, entries, strict=True)
            ),
            require_all_new=True,
            make_current=make_current,
        )
