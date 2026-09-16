"""Values stored by one localized operation catalog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocalizedOperationCopy:
    """One translated operation summary and best-use description."""

    summary: str
    best_for: str


def localized_copy(summary: str, best_for: str) -> LocalizedOperationCopy:
    """Construct one language-catalog entry without repeating its type name."""

    return LocalizedOperationCopy(summary=summary, best_for=best_for)


__all__ = ["LocalizedOperationCopy", "localized_copy"]
