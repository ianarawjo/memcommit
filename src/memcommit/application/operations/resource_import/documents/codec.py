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


def _identity(value: object) -> None:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("Native document identity must be a nonempty string.")


def decode_memory(record: object) -> Memory:
    if not isinstance(record, dict) or set(record) != {"type", "uid", "content"}:
        raise ValueError("Native Memory requires exactly type, uid, and content.")
    if record["type"] != "memory" or not isinstance(record["content"], str):
        raise ValueError("Native Memory must have type 'memory' and string content.")
    _identity(record["uid"])
    return Memory.from_dict(record)


def decode_context(record: object) -> Context:
    if not isinstance(record, dict) or not {"uid", "name", "memories"} <= set(record):
        raise ValueError("Native Context requires uid, name, and memories.")
    if set(record) - {"uid", "name", "memories", "order"}:
        raise ValueError("Native Context contains unsupported fields.")
    _identity(record["uid"])
    validate_portable_context_name(record["name"])
    items = record["memories"]
    if not isinstance(items, dict):
        raise ValueError("Native Context memories must be an object keyed by UID.")
    order = record.get("order", list(items))
    if (
        not isinstance(order, list)
        or any(not isinstance(uid, str) for uid in order)
        or len(order) != len(set(order))
        or set(order) != set(items)
    ):
        raise ValueError(
            "Native Context order must contain every item UID exactly once."
        )
    for uid, item in items.items():
        _identity(uid)
        if not isinstance(item, dict) or item.get("uid") != uid:
            raise ValueError("Native Context item UID must match its dictionary key.")
        kind = item.get("type")
        if kind == "memory":
            decode_memory(item)
        elif kind == "context_ref":
            if set(item) != {"type", "uid", "name"}:
                raise ValueError(
                    "Native Context reference contains unsupported fields."
                )
            validate_portable_context_name(item["name"])
        elif kind in {"memory_ref", "memory_snapshot_ref"}:
            reference = MemoryRef.from_dict(item)
            validate_portable_context_name(reference.target_context_name)
            if reference.to_dict() != item:
                raise ValueError(
                    "Native Memory reference is not losslessly importable."
                )
        else:
            # A file supplies data, never a live authority binding. Unknown
            # kinds must fail before Context.from_dict can silently omit them.
            raise ValueError(f"Unsupported native Context item type: {kind!r}.")
    return Context.from_dict(record)


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
