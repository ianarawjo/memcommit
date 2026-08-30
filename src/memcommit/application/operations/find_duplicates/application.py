"""Application boundary for provider-free ``find-duplicates`` discovery."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.authority.context_access import (
    resolve_context_access,
)
from memcommit.application.operations.dedup.application import (
    ExactDuplicateScopeReport,
    find_exact_duplicate_scope,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class FindDuplicatesRequest:
    context_name: str | None = None
    include_descendants: bool = False

    def __post_init__(self) -> None:
        if type(self.include_descendants) is not bool:
            raise TypeError("Find Duplicates descendant reach must be boolean.")


def find_duplicates(
    store: MemoryStore,
    request: FindDuplicatesRequest,
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
) -> ExactDuplicateScopeReport:
    """Resolve readable authority and inspect one exact or lexical scope."""

    access = resolve_context_access(
        store,
        request.context_name,
        current_name=current_name,
        required_permission="READ",
        registry=registry,
    )
    return find_exact_duplicate_scope(
        store,
        access,
        include_descendants=request.include_descendants,
        registry=registry,
    )


__all__ = ["FindDuplicatesRequest", "find_duplicates"]
