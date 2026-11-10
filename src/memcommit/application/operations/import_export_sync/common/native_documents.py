"""Decode native Context and Memory JSON without opening external references."""

from __future__ import annotations

from memcommit.core.context_name_validation import validate_context_name
from memcommit.models.context import Context
from memcommit.models.memory import Memory


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
