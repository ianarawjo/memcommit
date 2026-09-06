"""File-based Context and Memory import into the active Profile."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.profile.model._storage import (
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.resource_import._shared import (
    require_active_profile_snapshot,
)
from memcommit.application.operations.resource_import.context_data import (
    _closed_import_contexts,
    _context_name_mapping,
)
from memcommit.application.operations.resource_import.memory import (
    _memory_target_identity,
)
from memcommit.core.context import AutoCheckpoint, Memory
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.persistence.store import MemoryStore

from .codec import read_context_documents, read_document
from .publication import import_context_records


@dataclass(frozen=True)
class DocumentImportResult:
    source: Path
    target_contexts: tuple[str, ...]
    memory_uids: tuple[str, ...]


def import_context_from_documents(
    source: Path,
    *,
    source_name: str | None = None,
    target_name: str | None = None,
    recursive: bool = False,
) -> DocumentImportResult:
    documents = read_context_documents(source)
    names = tuple(document.value.name for document in documents)
    if source_name is None:
        if len(documents) == 1:
            source_name = names[0]
        elif not recursive or target_name is not None:
            raise ValueError(
                "Multiple Context documents require a source name, or --recursive without --as."
            )
    if source_name is not None:
        if source_name not in names:
            raise ValueError(f"Context {source_name!r} is absent from the JSON source.")
        selected = expand_lexical_context_names(
            ContextScope.create((source_name,), include_descendants=recursive),
            names,
        )
        documents = tuple(
            document for document in documents if document.value.name in selected
        )
        mapping = _context_name_mapping(
            selected, source_root=source_name, target_root=target_name or source_name
        )
    else:
        mapping = {name: name for name in names}
    contexts = _closed_import_contexts(
        tuple(document.value for document in documents), mapping
    )
    entries = tuple(
        (
            context,
            AutoCheckpoint(
                command="import",
                args={
                    "resource_kind": "context",
                    "source_kind": "JSON_FILE",
                    "source_sha256": document.sha256,
                    "source_context": document.value.name,
                    "source_context_uid": context.uid,
                    "target_context": context.name,
                },
                description=f"Imported native JSON Context '{document.value.name}' as '{context.name}'.",
            ),
        )
        for context, document in zip(contexts, documents, strict=True)
    )
    destination = MemoryStore()
    with authority_grant_snapshot_lock() as registry:
        require_active_profile_snapshot(registry, destination)
        created = import_context_records(destination, entries)
    return DocumentImportResult(
        Path(source),
        tuple(c.name for c in created),
        tuple(
            item.uid
            for context in created
            for item in context.iter_items()
            if isinstance(item, Memory)
        ),
    )


def import_memory_from_document(
    source: Path,
    *,
    memory_selector: str | None = None,
    target_context_locator: str | None = None,
) -> DocumentImportResult:
    destination = MemoryStore()
    target_name, target_uid = _memory_target_identity(
        destination, target_context_locator
    )
    document = read_document(source)
    memory = document.value
    if not isinstance(memory, Memory):
        raise ValueError(
            "Memory file import requires a standalone native Memory object."
        )
    if memory_selector is not None and not memory.uid.startswith(memory_selector):
        raise ValueError("Memory selector does not match the JSON document identity.")
    with authority_grant_snapshot_lock() as registry:
        require_active_profile_snapshot(registry, destination)
        target = destination.load_for_update(target_name)
        if target.uid != target_uid:
            raise ValueError("Memory import Target changed identity during resolution.")
        if memory.uid in target.memories:
            raise ValueError(
                f"Memory identity [{memory.uid[:8]}] already exists in Context {target.name!r}."
            )
        target.add(memory)
        destination.save(
            target,
            AutoCheckpoint(
                command="import",
                args={
                    "resource_kind": "memory",
                    "source_kind": "JSON_FILE",
                    "source_sha256": document.sha256,
                    "source_memory_uid": memory.uid,
                    "target_context": target.name,
                },
                description=f"Imported native JSON Memory [{memory.uid[:8]}] into Context '{target.name}'.",
            ),
        )
    return DocumentImportResult(Path(source), (target.name,), (memory.uid,))
