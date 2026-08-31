"""Typed read-only result for the Contexts operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ContextOwnership = Literal["OWNED", "GRANT"]


@dataclass(frozen=True)
class ContextCatalogEntry:
    """One public Context row with exact ownership provenance."""

    name: str
    current: bool
    ownership: ContextOwnership
    portable_name: bool
    capabilities: str | None = None
    authority_profile: str | None = None

    def __post_init__(self) -> None:
        if self.ownership == "OWNED":
            if self.capabilities is not None or self.authority_profile is not None:
                raise ValueError("Owned Context rows cannot carry Grant metadata.")
        elif not self.capabilities or not self.authority_profile:
            raise ValueError("Grant Context rows require capabilities and authority.")


@dataclass(frozen=True)
class ContextsCatalog:
    """One command-local hierarchy snapshot for orientation."""

    entries: tuple[ContextCatalogEntry, ...]
    has_local_contexts: bool
