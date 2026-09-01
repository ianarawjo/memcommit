"""Terminal-independent contracts for listing one readable Context scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.application.context_access.access import ContextAccess
from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
)
from memcommit.core.context import Context


@dataclass(frozen=True, slots=True)
class ListRequest:
    """One command-start-stable readable Context listing request."""

    context_locator: str | None
    current_context_name: str | None
    recursive: bool
    require_copyable_snapshot: bool = False

    def __post_init__(self) -> None:
        if self.context_locator is not None and (
            not isinstance(self.context_locator, str) or not self.context_locator.strip()
        ):
            raise ValueError("List Context locator must be nonblank text.")
        if self.current_context_name is not None and (
            not isinstance(self.current_context_name, str)
            or not self.current_context_name
        ):
            raise ValueError("List current Context name must be nonblank text.")
        if not isinstance(self.recursive, bool):
            raise TypeError("List recursive scope must be boolean.")
        if not isinstance(self.require_copyable_snapshot, bool):
            raise TypeError("List copyability requirement must be boolean.")


@dataclass(frozen=True, slots=True)
class ListSelection:
    """Frozen authorized input needed to build one List projection."""

    access: ContextAccess
    context: Context
    catalog: ReadableContextCatalog
    context_names: tuple[str, ...]
    readable_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.access.display_name != self.context.name:
            raise ValueError("List selection does not match its authorized Context.")
        if self.context.name not in self.context_names:
            raise ValueError("List selection omitted its authorized Context name.")
        if len(self.context_names) != len(set(self.context_names)):
            raise ValueError("List selection repeats a readable Context name.")
        if len(self.readable_uids) != len(set(self.readable_uids)):
            raise ValueError("List selection repeats a readable object UID.")


class ListSourcePort(Protocol):
    """Authorize and freeze one readable List source."""

    def freeze(self, request: ListRequest) -> ListSelection: ...


def run_list(request: ListRequest, *, source: ListSourcePort) -> ListSelection:
    """Freeze one List source without terminal or clipboard effects."""

    if not isinstance(request, ListRequest):
        raise TypeError("List requires a ListRequest.")
    selection = source.freeze(request)
    if not isinstance(selection, ListSelection):
        raise TypeError("List source returned an invalid selection.")
    return selection


__all__ = [
    "ListRequest",
    "ListSelection",
    "ListSourcePort",
    "run_list",
]

