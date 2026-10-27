"""Decode native Context and Memory JSON without opening external references."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.persistence.store.infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
)


@dataclass(frozen=True)
class NativeDocument:
    path: Path
    sha256: str
    value: Context | Memory


from memcommit.core.context_name_validation import validate_context_name


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
    if set(record) - {"uid", "name", "memories", "order", "document", "attached_files"}:
        raise ValueError("Native Context contains unsupported fields.")
    _identity(record["uid"])
    validate_context_name(record["name"])
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
        decode_memory(item)
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
