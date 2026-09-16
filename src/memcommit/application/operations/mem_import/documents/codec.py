"""Decode native Context and Memory JSON without opening external references."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from memcommit.core.context import Context, Memory, MemoryRef
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store.infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
)


@dataclass(frozen=True)
class NativeDocument:
    path: Path
    sha256: str
    value: Context | Memory


from memcommit.application.capabilities.import_export.formats.mem import decode_memory, decode_context


def read_document(path: Path) -> NativeDocument:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Native document is not a regular file: {path}.")
    data = path.read_bytes()
    record = json.loads(data, object_pairs_hook=_reject_duplicate_json_keys)
    value = (
        decode_memory(record)
        if isinstance(record, dict) and record.get("type") == "memory"
        else decode_context(record)
    )
    return NativeDocument(path, hashlib.sha256(data).hexdigest(), value)


def read_context_documents(source: Path) -> tuple[NativeDocument, ...]:
    """Read one file or a tree of context.json files; never follow record paths."""
    source = Path(source)
    paths = (
        tuple(sorted(source.rglob("context.json"))) if source.is_dir() else (source,)
    )
    if not paths:
        raise ValueError("Native Context source contains no context.json files.")
    documents = tuple(read_document(path) for path in paths)
    if any(not isinstance(document.value, Context) for document in documents):
        raise ValueError("Context import requires native Context documents.")
    names = [document.value.name for document in documents]
    uids = [document.value.uid for document in documents]
    if len(names) != len(set(names)) or len(uids) != len(set(uids)):
        raise ValueError("Native Context source repeats a Context name or identity.")
    return documents
