"""Stable public result values for read-only Show inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


@dataclass(frozen=True, slots=True)
class ShowSourceResult:
    """Operation-neutral access, reach, form, and availability facts."""

    access: str
    reach: str
    form: str
    states: tuple[str, ...]
    permissions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ShowMemoryResult:
    uid: str
    context_name: str
    content: str
    source: ShowSourceResult
    kind: Literal["memory"] = "memory"


@dataclass(frozen=True, slots=True)
class ShowMemoryReferenceResult:
    uid: str
    context_name: str
    target_context_uid: str
    target_context_name: str
    target_memory_uid: str
    resolved: bool
    content: str | None
    source: ShowSourceResult
    kind: Literal["memory_ref"] = "memory_ref"


@dataclass(frozen=True, slots=True)
class ShowQueryViewResult:
    uid: str
    context_name: str
    name: str
    source: ShowSourceResult
    kind: Literal["query_view"] = "query_view"


@dataclass(frozen=True, slots=True)
class ShowEmbeddedContextResult:
    uid: str
    context_name: str
    name: str
    source: ShowSourceResult
    kind: Literal["context"] = "context"


ShowDirectItemResult: TypeAlias = (
    ShowMemoryResult
    | ShowMemoryReferenceResult
    | ShowQueryViewResult
    | ShowEmbeddedContextResult
)


@dataclass(frozen=True, slots=True)
class ShowContextResult:
    uid: str
    name: str
    items: tuple[ShowDirectItemResult, ...]
    source: ShowSourceResult
    kind: Literal["context"] = "context"


ShowResult: TypeAlias = (
    ShowContextResult
    | ShowMemoryResult
    | ShowMemoryReferenceResult
    | ShowQueryViewResult
)


__all__ = [
    "ShowContextResult",
    "ShowDirectItemResult",
    "ShowEmbeddedContextResult",
    "ShowMemoryReferenceResult",
    "ShowMemoryResult",
    "ShowQueryViewResult",
    "ShowResult",
    "ShowSourceResult",
]
