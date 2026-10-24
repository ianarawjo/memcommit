"""Freeze the local Context namespace used by an operation's selectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.application.context_access.access import ContextAccess
from memcommit.models.context import Context
from memcommit.persistence.store.lookup.context_names import (
    sort_context_names,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class ProfileContextNavigation:
    """A captured local Context tree and the catalog that loads its rows."""

    catalog: ReadableContextCatalog
    local_names: tuple[str, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return self.local_names


class ReadableContextCatalog:
    """A frozen local namespace bound to the operation's captured Store."""

    def __init__(self, active_store: MemoryStore, root_access: ContextAccess):
        self._active_store = active_store
        self._names = tuple(active_store.list_context_names())
        self._bindings = {
            name: ContextAccess(active_store, name, name) for name in self._names
        }
        if root_access.access_name not in self._bindings:
            raise FileNotFoundError(
                f"Context '{root_access.access_name}' is outside the captured namespace."
            )

    def list_context_names(
        self,
        *,
        sort_order: Literal["hierarchical", "alphabetical"] = "hierarchical",
    ) -> list[str]:
        return list(sort_context_names(self._names, sort_order=sort_order))

    def context_exists(self, name: str) -> bool:
        return name in self._bindings

    def access_for(self, name: str) -> ContextAccess:
        try:
            return self._bindings[name]
        except KeyError as error:
            raise FileNotFoundError(
                f"Context '{name}' is outside the captured namespace."
            ) from error

    def load_direct(self, name: str) -> Context:
        access = self.access_for(name)
        return access.store.load_direct(access.context_name)

    def load(self, name: str) -> Context:
        return self.load_direct(name)


def freeze_readable_context_catalog(
    active_store: MemoryStore,
    root_access: ContextAccess,
) -> ReadableContextCatalog:
    """Capture the local namespace before constructing an operation request."""
    return ReadableContextCatalog(active_store, root_access)


def freeze_profile_readable_context_catalog(
    active_store: MemoryStore,
    selected_access: ContextAccess,
) -> ReadableContextCatalog:
    """Capture the Profile namespace for an explicit Profile-wide selector."""
    return ReadableContextCatalog(active_store, selected_access)


def freeze_profile_context_navigation(
    active_store: MemoryStore,
    selected_access: ContextAccess,
) -> ProfileContextNavigation:
    catalog = freeze_profile_readable_context_catalog(active_store, selected_access)
    return ProfileContextNavigation(catalog, tuple(catalog.list_context_names()))
