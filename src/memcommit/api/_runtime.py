"""Internal immutable dependencies shared by public operation adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from memcommit.api.query import QueryProviderConfig
from memcommit.operations.profile.config import ProfileEntry, ProfileRegistry
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True, slots=True)
class ClientRuntime:
    """One client-owned Store, Profile, configuration, and provider snapshot.

    Operation adapters receive this value instead of importing or retaining the
    public ``MemCommitClient``. That keeps the facade dependency pointing into
    operation assembly and prevents operation modules from reaching back out.
    """

    store: MemoryStore
    store_root: Path
    registry: ProfileRegistry | None
    profile: ProfileEntry | None
    query_config: QueryProviderConfig
    ordinary_provider_factory: Callable[[], object]
    query_route_provider_factory: Callable[[str], object]
    semantic_provider_factory: Callable[[], object]


__all__ = ["ClientRuntime"]

