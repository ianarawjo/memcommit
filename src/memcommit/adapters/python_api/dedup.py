"""Stable public values for provider-free exact Dedup."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExactDedupGroupResult:
    survivor_uid: str
    absorbed_uids: tuple[str, ...]
    content: str | None
    item_kind: str = "MEMORY"
    summary: str = ""
    context_name: str | None = None


@dataclass(frozen=True)
class ExactDedupContextResult:
    """One direct Context effect inside an exact-Dedup scope."""

    context_name: str
    groups: tuple[ExactDedupGroupResult, ...]
    checkpoint_uid: str | None

    @property
    def removed_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class ExactDedupResult:
    context_name: str
    groups: tuple[ExactDedupGroupResult, ...]
    checkpoint_uid: str | None
    include_descendants: bool = False
    contexts: tuple[ExactDedupContextResult, ...] = ()
    checkpoint_uids: tuple[str, ...] = ()
    operation_uid: str | None = None

    @property
    def removed_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class ExactDuplicateFindResult:
    """Read-only exact DUP report for one direct Context."""

    context_name: str
    memory_count: int
    groups: tuple[ExactDedupGroupResult, ...]
    item_count: int = 0
    include_descendants: bool = False
    contexts: tuple["ExactDuplicateContextResult", ...] = ()

    @property
    def duplicate_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class ExactDuplicateContextResult:
    """Read-only exact groups for one independently judged direct Context."""

    context_name: str
    context_uid: str
    memory_count: int
    item_count: int
    groups: tuple[ExactDedupGroupResult, ...]

    @property
    def duplicate_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


__all__ = [
    "ExactDedupGroupResult",
    "ExactDedupContextResult",
    "ExactDedupResult",
    "ExactDuplicateContextResult",
    "ExactDuplicateFindResult",
]
