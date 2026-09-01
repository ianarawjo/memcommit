"""Shared readable-Context assembly for public client operations."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.application.context_access.access import ContextAccess, resolve_context_access
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_readable_context_catalog,
    freeze_readable_context_catalog,
)
from memcommit.application.operations.profile.config import load_profile_registry, profile_store_dir
from memcommit.application.operations.profile.model import authority_grant_snapshot_lock
from memcommit.persistence.store import MemoryStore


class LocalReadableCatalog:
    """Readable catalog that never consults global Profile configuration."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def list_context_names(self) -> list[str]:
        return self._store.list_context_names()

    def context_exists(self, name: str) -> bool:
        return self._store.context_exists(name)

    def load_direct(self, name: str):
        return self._store.load_direct(name)

    def load(self, name: str):
        return self._store.load(name)

    def access_for(self, name: str) -> ContextAccess:
        if not self._store.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' is outside the view.")
        return ContextAccess(
            store=self._store,
            context_name=name,
            display_name=name,
            attachment_name=None,
            permission="READ",
        )


def active_client_registry(runtime: ClientRuntime):
    """Return the live registry only when it owns the client's frozen Store."""

    if runtime.registry is None or runtime.profile is None:
        return None
    registry = load_profile_registry()
    if (
        registry.active.uid != runtime.profile.uid
        or runtime.store_root != profile_store_dir(registry.active).resolve()
    ):
        return None
    return registry


def freeze_client_readable_catalog(
    runtime: ClientRuntime,
    target_names: tuple[str, ...],
    *,
    current_name: str | None,
    include_query_routes: bool,
):
    """Freeze one public-client namespace without importing an interface."""

    configured_registry = active_client_registry(runtime)
    if configured_registry is None:
        if any(not runtime.store.context_exists(name) for name in target_names):
            raise FileNotFoundError(
                "An explicit-root client can read only Contexts in its own Store."
            )
        return LocalReadableCatalog(runtime.store)

    # Resolve every operand against the same current snapshot and one Grant
    # revision. Callers construct any provider only after this function returns.
    with authority_grant_snapshot_lock() as live_registry:
        if live_registry.active.uid != configured_registry.active.uid:
            raise RuntimeError("The active Profile changed during Context selection.")
        accesses = tuple(
            resolve_context_access(
                runtime.store,
                name,
                current_name=current_name,
                required_permission="READ",
                registry=live_registry,
            )
            for name in target_names
        )
        if len(accesses) > 1:
            catalog = freeze_profile_readable_context_catalog(
                runtime.store,
                accesses[0],
                include_query_routes=include_query_routes,
            )
            for access in accesses:
                catalog.access_for(access.display_name)
            return catalog
        return freeze_readable_context_catalog(
            runtime.store,
            accesses[0],
            include_query_routes=include_query_routes,
        )


__all__ = [
    "LocalReadableCatalog",
    "active_client_registry",
    "freeze_client_readable_catalog",
]
