"""Shared resolution for one Memory-focused semantic operation.

The selected Memory is the operation's actionable frame.  Other Memories in
the already frozen Context frame may be supplied separately as contextual
evidence, but this module never promotes them into the actionable selection.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, TypeVar


class MemoryIdentity(Protocol):
    """The narrow identity required from a Memory or provider candidate."""

    uid: str


MemoryValue = TypeVar("MemoryValue", bound=MemoryIdentity)


class MemoryFocusError(ValueError):
    """One Memory selector did not identify an exact member of its frame."""


@dataclass(frozen=True)
class MemoryFocus:
    """An exact actionable selection and its non-actionable neighbors."""

    selected_uid: str | None
    actionable: tuple[MemoryValue, ...]
    context_only: tuple[MemoryValue, ...]


def resolve_memory_focus(
    values: Iterable[MemoryValue],
    selector: str | None,
    *,
    label: str = "Memory",
) -> MemoryFocus:
    """Resolve an optional UID/prefix against one frozen ordered frame.

    With no selector, the complete frame remains actionable and no separate
    contextual-evidence set is created.  With a selector, exactly one value is
    actionable and every other frozen value becomes context-only evidence.
    """

    frozen = tuple(values)
    if selector is None:
        return MemoryFocus(
            selected_uid=None,
            actionable=frozen,
            context_only=(),
        )
    identities = tuple(value.uid for value in frozen)
    if len(identities) != len(set(identities)):
        raise MemoryFocusError(f"{label} frame contains duplicate uids.")
    if not isinstance(selector, str) or not selector:
        raise MemoryFocusError(f"{label} selector must be a non-empty uid prefix.")
    matches = tuple(value for value in frozen if value.uid.startswith(selector))
    if not matches:
        raise MemoryFocusError(
            f"No {label} has a uid starting with '{selector}'."
        )
    if len(matches) > 1:
        raise MemoryFocusError(
            f"Ambiguous prefix '{selector}' matches {len(matches)} {label}s: "
            + ", ".join(value.uid[:8] for value in matches)
        )
    selected = matches[0]
    return MemoryFocus(
        selected_uid=selected.uid,
        actionable=(selected,),
        context_only=tuple(value for value in frozen if value.uid != selected.uid),
    )
