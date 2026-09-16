"""Operation-neutral exact-or-unique-prefix UID resolution."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar


T = TypeVar("T")


_CANONICAL_UUID_SHAPE = "00000000-0000-0000-0000-000000000000"


def is_memory_uid_prefix(value: object) -> bool:
    """Return whether text is any nonempty canonical UUID prefix.

    This broader predicate supports an operation that already has a safe
    storage-backed disambiguation path. It must not replace
    :func:`is_memory_uid_selector` in storage-independent overloaded operand
    classification, where fewer than eight characters can still be a Context
    name.
    """

    if not isinstance(value, str) or not 1 <= len(value) <= 36:
        return False
    folded = value.casefold()
    for index, character in enumerate(folded):
        expected = _CANONICAL_UUID_SHAPE[index]
        if expected == "-":
            if character != "-":
                return False
        elif character not in "0123456789abcdef":
            return False
    return True


def is_memory_uid_selector(value: object) -> bool:
    """Return whether text has the unambiguous public UUID-prefix shape.

    Automatic operand classification starts at the eight-character prefix
    shown by the CLI. Shorter prefixes remain available behind explicit
    operation options, where their Memory role is already known.
    """

    return isinstance(value, str) and len(value) >= 8 and is_memory_uid_prefix(value)


class UidLocatorError(ValueError):
    """Base error for a UID selector that cannot name one frozen candidate."""


class UidLocatorUnavailableError(UidLocatorError):
    """The selector does not match any candidate in the frozen catalog."""


class UidLocatorAmbiguousError(UidLocatorError):
    """The selector matches more than one candidate in the frozen catalog."""


def resolve_exact_or_unique_uid(
    candidates: Iterable[T],
    selector: str,
    *,
    uid: Callable[[T], str],
    label: str,
) -> T:
    """Resolve an exact UID first, otherwise one unambiguous UID prefix.

    Callers freeze and authorize their own candidate namespace before invoking
    this helper. Keeping catalog ownership outside the resolver prevents a UID
    that is valid in one operation from silently selecting another artifact.
    """

    if not isinstance(selector, str) or not selector.strip():
        raise UidLocatorUnavailableError(f"{label} UID must be nonblank text.")
    value = selector.strip()
    frozen = tuple(candidates)
    exact = tuple(candidate for candidate in frozen if uid(candidate) == value)
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise UidLocatorAmbiguousError(
            f"{label} UID '{value}' is ambiguous; pass a longer UID."
        )
    matches = tuple(
        candidate for candidate in frozen if uid(candidate).startswith(value)
    )
    if not matches:
        raise UidLocatorUnavailableError(f"{label} UID '{value}' is unavailable.")
    if len(matches) > 1:
        raise UidLocatorAmbiguousError(
            f"{label} UID prefix '{value}' matches {len(matches)} candidates; "
            "pass a longer UID."
        )
    return matches[0]
