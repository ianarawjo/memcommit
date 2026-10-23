"""Validate, rewrite, and digest persisted Context records."""

from __future__ import annotations
import hashlib
import json
from memcommit.persistence.store.context_memory.checkpoint_frame_mapping import (
    map_restorable_checkpoint_frames,
)
from memcommit.models.context import Context


def canonical_context_record(
    value: Context | dict[str, object],
) -> dict[str, object]:
    """Return one normalized logical direct Context record."""
    if isinstance(value, Context):
        return value.to_dict()
    # Normalize the Memory frame before hashing snapshot contents.
    return Context.from_dict(value).to_dict()


def context_record_digest(value: Context | dict[str, object]) -> str:
    """Hash one complete logical direct Context record canonically."""
    record = canonical_context_record(value)
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def checkpoint_history_digest(entries: list[dict]) -> str:
    """Hash one newest-first physical checkpoint frame canonically."""
    try:
        encoded = json.dumps(
            entries,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("Checkpoint history contains invalid data.") from error
    return hashlib.sha256(encoded).hexdigest()


def _mapped_context_name(name: str, old_root: str, new_root: str) -> str | None:
    """Return the slash-boundary prefix mapping, or ``None`` when unrelated."""
    if name == old_root:
        return new_root
    prefix = old_root + "/"
    if name.startswith(prefix):
        return new_root + name[len(old_root) :]
    return None


def _validate_context_header(data: object, expected_name: str) -> dict:
    """Validate the minimum Context JSON structure needed for safe loading."""
    if not isinstance(data, dict):
        raise ValueError(
            f"Context file for '{expected_name}' must contain a JSON object."
        )
    if data.get("name") != expected_name:
        raise ValueError(
            f"Context file for '{expected_name}' declares a different name "
            f"('{data.get('name')}')."
        )
    if not isinstance(data.get("uid"), str) or not data["uid"]:
        raise ValueError(f"Context file for '{expected_name}' has no valid uid.")
    if not isinstance(data.get("memories"), dict):
        raise ValueError(
            f"Context file for '{expected_name}' has no valid memories object."
        )
    return data


def validate_checkpoint_context_frames(value: dict[str, object]) -> None:
    """Validate every Context frame that ordinary history can restore."""
    map_restorable_checkpoint_frames(
        value, lambda frame: Context.from_dict(frame).to_dict()
    )
