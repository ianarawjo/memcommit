"""Stable public values for provider-backed semantic Search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SearchMode = Literal["CURRENT", "HISTORY"]
SearchResultKind = Literal[
    "memory",
    "ref",
    "query",
    "artifact",
    "memory_version",
    "memory_transition",
    "checkpoint",
]
SearchRelevance = Literal["primary", "related"]


@dataclass(frozen=True, slots=True)
class SearchItemResult:
    """One authorized result returned in semantic relevance order."""

    context_name: str
    kind: SearchResultKind
    uid: str
    content: str
    relevance: SearchRelevance
    source_context_name: str | None = None
    source_context_uid: str | None = None
    source_memory_uid: str | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One complete read-only semantic Search outcome."""

    query: str
    context_names: tuple[str, ...]
    include_descendants: bool
    follow_embeds: bool
    mode: SearchMode
    items: tuple[SearchItemResult, ...]
    related_query: str = ""


__all__ = [
    "SearchItemResult",
    "SearchMode",
    "SearchRelevance",
    "SearchResult",
    "SearchResultKind",
]
