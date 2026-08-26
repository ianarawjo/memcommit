"""Terminal-independent request and result contract for Clear."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClearRequest:
    """One exact or lexical-subtree Clear request."""

    context_locator: str | None = None
    recursive: bool = False

    def __post_init__(self) -> None:
        if self.context_locator is not None and (
            not isinstance(self.context_locator, str) or not self.context_locator
        ):
            raise ValueError("Clear Context locator must be nonempty text.")


@dataclass(frozen=True)
class ClearResult:
    """Complete durable or no-change outcome for Clear."""

    context_name: str
    recursive: bool
    item_count: int
    scope_count: int
    changed_context_count: int

    @property
    def changed(self) -> bool:
        return self.item_count > 0
