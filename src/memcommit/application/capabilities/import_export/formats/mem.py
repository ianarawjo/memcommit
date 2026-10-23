"""Lossless mem-record validation shared by native Import and Export."""

from __future__ import annotations
import json
import hashlib
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.core.context_name_validation import validate_context_name
from ..model import MemContent, OutputFile, fail


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


def _unique_pairs(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError(f"Duplicate JSON key: {key}")
        record[key] = value
    return record


def decode_mem(files):
    contexts = []
    attached = {}
    for file in files:
        if file.path.endswith("context.json"):
            contexts.append(
                decode_context(json.loads(file.data, object_pairs_hook=_unique_pairs))
            )
        elif file.path.startswith("attached-files/"):
            attached[hashlib.sha256(file.data).hexdigest()] = file.data
        else:
            fail(
                "unsupported-mem-file",
                file.path,
                "Expected context.json records or attached-files content.",
            )
    content = MemContent(tuple(contexts), attached)
    validate_mem(content)
    return content


def validate_mem(content):
    contexts = tuple(decode_context(c.to_dict()) for c in content.contexts)
    names = {c.name: c for c in contexts}
    if len(names) != len(contexts) or len({c.uid for c in contexts}) != len(contexts):
        fail("duplicate-context", "mem", "Context names and identities must be unique.")
    for context in contexts:
        for file in context.asset_metadata:
            data = content.attached_data.get(file.sha256)
            if data is None or hashlib.sha256(data).hexdigest() != file.sha256:
                fail(
                    "missing-attachment",
                    file.path,
                    "Attached-file bytes are missing or damaged.",
                )
    return content


def encode_mem(content):
    validate_mem(content)
    files = [
        OutputFile(
            f"contexts/{c.name}/context.json",
            (json.dumps(c.to_dict(), ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            ),
        )
        for c in content.contexts
    ]
    files.extend(
        OutputFile(f"attached-files/{digest}", data, True)
        for digest, data in sorted(content.attached_data.items())
    )
    return tuple(files)
