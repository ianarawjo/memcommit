"""Shared validation rules for Context names."""

from __future__ import annotations

import re

from memcommit.core.context_targeting.uid_locator import is_memory_uid_selector


_CONTEXT_NAME_SEGMENT = re.compile(r"[.A-Za-z0-9][A-Za-z0-9._-]*\Z")
_WINDOWS_RESERVED_SEGMENT_ROOTS = frozenset(
    {
        "aux",
        "con",
        "nul",
        "prn",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
)
RESERVED_CONTEXT_SEGMENTS = frozenset({"context.json", "checkpoints"})


def validate_context_name(value: object) -> str:
    """Return a valid Context name or raise ValueError."""

    if not isinstance(value, str) or not value:
        raise ValueError("Context name must be non-empty text.")
    parts = tuple(value.split("/"))
    if any(not part for part in parts):
        raise ValueError(
            f"Invalid context name {value!r}: not portable; leading, trailing, or "
            "repeated '/' is not allowed."
        )
    for part in parts:
        if _CONTEXT_NAME_SEGMENT.fullmatch(part) is None:
            raise ValueError(
                f"Invalid context name {value!r}: not portable; segment {part!r} "
                "must start with an ASCII letter, digit, or named dot prefix and contain only "
                "ASCII letters, digits, '.', '_', or '-'."
            )
        if part in {".", ".."}:
            raise ValueError(
                f"Invalid context name {value!r}: navigation segment {part!r} "
                "cannot be a durable Context name."
            )
        folded = part.casefold()
        if folded in RESERVED_CONTEXT_SEGMENTS:
            raise ValueError(
                f"Invalid context name {value!r}: not portable; segment {part!r} "
                "is reserved for Context storage."
            )
        if part.endswith("."):
            raise ValueError(
                f"Invalid context name {value!r}: not portable; segment {part!r} "
                "must not end with '.'."
            )
        if part.split(".", 1)[0].casefold() in _WINDOWS_RESERVED_SEGMENT_ROOTS:
            raise ValueError(
                f"Invalid context name {value!r}: not portable; segment {part!r} "
                "uses a reserved Windows device name."
            )
    # A whole root with this shape is indistinguishable from the public
    # positional Memory-selector grammar. Nested names retain their slash and
    # therefore remain typed as Context locators; parent creation validates
    # each planned root separately.
    if is_memory_uid_selector(value):
        raise ValueError(
            f"Invalid context name {value!r}: not portable; a Context name "
            "must not have the shape of a Memory UUID or visible UID prefix."
        )
    return value


def is_context_name_valid(value: object) -> bool:
    """Return whether the Context name follows the shared rules."""

    try:
        validate_context_name(value)
    except ValueError:
        return False
    return True


__all__ = [
    "RESERVED_CONTEXT_SEGMENTS",
    "is_context_name_valid",
    "validate_context_name",
]
