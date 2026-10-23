"""Publish native Context data through the ordinary require-new transaction."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from memcommit.application.operations.mem_import.context_data import (
    remap_imported_context_names,
    _reject_context_identity_collisions,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.attached_files import save_attached_file

from .codec import decode_context


def publish_document_import(destination, request, content):
    """Retain document bytes and checkpoints after the caller authorizes its Store.

    Ordinary Import holds its active-Profile authority snapshot. Profile creation
    instead owns an unpublished staging Store under the registry lock.
    """
    from memcommit.application.operations.mem_import.application import ImportResult

    # Retain immutable bytes before any Context can reference them.
    for digest, data in content.attached_data.items():
        if save_attached_file(store_root=destination.store_dir, data=data) != digest:
            raise ValueError("Attached-file identity mismatch.")
    entries = tuple(
        (
            context,
            AutoCheckpointRequest(
                command="import",
                command_details={"resource_kind": "document", "target_context": context.name},
            ),
        )
        for context in content.contexts
    )
    created = (
        import_context_records(destination=destination, entries=entries)
        if entries
        else ()
    )
    checkpoints = tuple(
        str(item["uid"])
        for context in created
        for item in destination.list_checkpoints(context.name)
    )
    files = []
    for context in created:
        if (
            context.corresponding_document_metadata
            and context.corresponding_document_metadata.role != "package"
        ):
            files.append(
                (context.corresponding_document_metadata.path, "DOCUMENT", context.name)
            )
        files.extend(
            (file.path, "ATTACHED", context.name) for file in context.asset_metadata
        )
    return ImportResult(
        source=Path(request.source),
        target_contexts=tuple(context.name for context in created),
        files=tuple(files),
        memory_count=sum(
            isinstance(item, Memory)
            for context in created
            for item in context.iter_memories()
        ),
        checkpoints=checkpoints,
    )


def import_context_records(
    destination: MemoryStore,
    entries: Iterable[tuple[Context, AutoCheckpointRequest | None]],
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
    imported = remap_imported_context_names(contexts, {name: name for name in names})
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
