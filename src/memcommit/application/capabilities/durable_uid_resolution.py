"""Resolve durable UID selectors inside one caller-authorized candidate frame.

The resolver deliberately does not enumerate storage. Each operation freezes
the identities it is allowed to disclose, then supplies only that bounded
catalog here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from memcommit.core.context_targeting.uid_locator import is_memory_uid_selector


T = TypeVar("T")
_PUBLIC_UID_PREFIX_LENGTH = 8


class DurableUidResolutionError(ValueError):
    """A durable UID selector cannot be resolved safely."""


class DurableUidAmbiguityError(DurableUidResolutionError):
    """A prefix names more than one durable identity in the frozen frame."""


@dataclass(frozen=True, slots=True)
class DurableUidCandidate(Generic[T]):
    """One typed, already-authorized durable identity and its caller value."""

    uid: str
    kind: str
    value: T

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise DurableUidResolutionError("Durable UID candidates require a UID.")
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise DurableUidResolutionError("Durable UID candidates require a kind.")


@dataclass(frozen=True, slots=True)
class DurableUidResolution(Generic[T]):
    """Every occurrence of one exact durable identity in frame order."""

    selector: str
    uid: str
    candidates: tuple[DurableUidCandidate[T], ...]

    def __post_init__(self) -> None:
        if not self.candidates or any(
            candidate.uid != self.uid for candidate in self.candidates
        ):
            raise DurableUidResolutionError(
                "A durable UID resolution must contain one exact identity."
            )

    @property
    def values(self) -> tuple[T, ...]:
        return tuple(candidate.value for candidate in self.candidates)


def try_resolve_durable_uid(
    candidates: tuple[DurableUidCandidate[T], ...],
    selector: str,
) -> DurableUidResolution[T] | None:
    """Resolve exact identity first, then one unambiguous public UID prefix."""

    if not isinstance(selector, str) or not selector.strip():
        return None
    value = selector.strip()
    exact = tuple(candidate for candidate in candidates if candidate.uid == value)
    if exact:
        return DurableUidResolution(value, value, exact)
    if len(value) < _PUBLIC_UID_PREFIX_LENGTH or any(
        character.isspace() for character in value
    ):
        return None
    matching_uids = {
        candidate.uid for candidate in candidates if candidate.uid.startswith(value)
    }
    if not matching_uids:
        return None
    if len(matching_uids) > 1:
        raise DurableUidAmbiguityError(
            f"UID prefix {value!r} matches {len(matching_uids)} readable "
            "identities; pass a longer UID."
        )
    uid = next(iter(matching_uids))
    matches = tuple(candidate for candidate in candidates if candidate.uid == uid)
    return DurableUidResolution(value, uid, matches)


def is_unresolved_uid_selector(value: object) -> bool:
    """Return whether an unmatched input is still clearly a public UID selector."""

    return is_memory_uid_selector(value) or (
        isinstance(value, str)
        and len(value.strip()) >= _PUBLIC_UID_PREFIX_LENGTH
        and ":" in value
        and not any(character.isspace() for character in value)
    )


__all__ = [
    "DurableUidAmbiguityError",
    "DurableUidCandidate",
    "DurableUidResolution",
    "DurableUidResolutionError",
    "is_unresolved_uid_selector",
    "try_resolve_durable_uid",
]
