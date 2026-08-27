"""Operation-neutral exact-or-unique-prefix UID resolution."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar


T = TypeVar("T")


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
    matches = tuple(candidate for candidate in frozen if uid(candidate).startswith(value))
    if not matches:
        raise UidLocatorUnavailableError(
            f"{label} UID '{value}' is unavailable."
        )
    if len(matches) > 1:
        raise UidLocatorAmbiguousError(
            f"{label} UID prefix '{value}' matches {len(matches)} candidates; "
            "pass a longer UID."
        )
    return matches[0]
