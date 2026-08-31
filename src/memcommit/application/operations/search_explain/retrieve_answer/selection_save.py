"""Shared adaptation helpers for saving retrieved Memory selections."""

from __future__ import annotations

from typing import Protocol

from memcommit.application.capabilities.authority.context_access import ContextAccess
from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextFromSelectionError,
)


class RetrieveAnswerSelectionCatalog(Protocol):
    """Frozen public bindings used by one Retrieve & Answer operation."""

    def access_for(self, name: str) -> ContextAccess: ...


def resolve_selection_source_public_name(
    catalog: RetrieveAnswerSelectionCatalog,
    *,
    containing_name: str,
    source_name: str,
    is_reference: bool,
) -> str:
    """Map an authority-side Memory owner into the frozen public tree."""

    try:
        catalog.access_for(source_name)
        return source_name
    except FileNotFoundError:
        pass
    if not is_reference:
        raise SaveContextFromSelectionError(
            f"Source Context '{source_name}' left the readable view."
        )
    containing = catalog.access_for(containing_name)
    if not containing.is_granted or containing.view is None:
        raise SaveContextFromSelectionError(
            f"Referenced source Context '{source_name}' is not readable."
        )
    grant = containing.view.grant
    if source_name == grant.resource_name:
        public_name = grant.public_name
    elif source_name.startswith(grant.resource_name + "/"):
        public_name = grant.public_name + source_name[len(grant.resource_name) :]
    else:
        raise SaveContextFromSelectionError(
            "The referenced Memory target is outside its readable Grant resource."
        )
    catalog.access_for(public_name)
    return public_name


__all__ = [
    "RetrieveAnswerSelectionCatalog",
    "resolve_selection_source_public_name",
]
