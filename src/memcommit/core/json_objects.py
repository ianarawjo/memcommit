"""Pure JSON construction and persisted-representation primitives."""

from __future__ import annotations

import hashlib
import json


def canonical_json_digest(value: object) -> str:
    """Hash compact sorted UTF-8 JSON without normalizing the caller's values."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Keep object order and reject ambiguous keys before schema validation."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result
