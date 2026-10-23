"""Shared adaptation helpers for saving retrieved Memory selections."""

from __future__ import annotations

from typing import Protocol

from memcommit.application.context_access.access import ContextAccess


class RetrieveAnswerSelectionCatalog(Protocol):
    """Frozen public bindings used by one Retrieve & Answer operation."""

    def access_for(self, name: str) -> ContextAccess: ...


def resolve_selection_source_public_name(
    catalog: RetrieveAnswerSelectionCatalog,
    *,
    source_name: str,
) -> str:
    """Map an authority-side Memory owner into the frozen public tree."""

    catalog.access_for(source_name)
    return source_name


__all__ = [
    "RetrieveAnswerSelectionCatalog",
    "resolve_selection_source_public_name",
]
