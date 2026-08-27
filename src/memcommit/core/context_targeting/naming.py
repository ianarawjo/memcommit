"""Portable names for newly published Context namespace identities.

Legacy stores may contain broader names because storage safety and shell
portability were historically the same validation boundary.  Keep this module
independent from Store I/O so creation, import, Grant, and migration adapters
can share one portable-name contract without making legacy records unreadable.
"""
from __future__ import annotations

import re

from memcommit.core.context_targeting.memory_focus import is_memory_uid_selector


_PORTABLE_CONTEXT_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
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


def validate_portable_context_name(value: object) -> str:
    """Return one shell- and filesystem-portable slash-delimited name.

    The first character rule prevents a complete locator from being parsed as
    a CLI option.  Restricting every later character to the portable filename
    set means ordinary names never need shell grouping or expansion escaping.
    Slash remains the only namespace separator.

    This validator is intentionally for *new* identities and rename
    destinations.  Existing broader names stay readable through the legacy
    storage validator until an explicit graph migration changes them.
    """

    if not isinstance(value, str) or not value:
        raise ValueError("Context name must be non-empty text.")
    parts = tuple(value.split("/"))
    if any(not part for part in parts):
        raise ValueError(
            f"Invalid context name {value!r}: not portable; leading, trailing, or "
            "repeated '/' is not allowed."
        )
    for part in parts:
        if _PORTABLE_CONTEXT_SEGMENT.fullmatch(part) is None:
            raise ValueError(
                f"Invalid context name {value!r}: not portable; segment {part!r} "
                "must start with an ASCII letter or digit and contain only "
                "ASCII letters, digits, '.', '_', or '-'."
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


def is_portable_context_name(value: object) -> bool:
    """Return whether ``value`` satisfies the new-identity name contract."""

    try:
        validate_portable_context_name(value)
    except ValueError:
        return False
    return True


__all__ = [
    "RESERVED_CONTEXT_SEGMENTS",
    "is_portable_context_name",
    "validate_portable_context_name",
]
