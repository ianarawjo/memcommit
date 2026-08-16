"""Stable public values for provider-free deterministic Find."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FindMode = Literal["LITERAL", "REGEX"]
FindItemKind = Literal["memory", "memory_ref"]


@dataclass(frozen=True, slots=True)
class FindSpanResult:
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class FindMatchResult:
    context_name: str
    context_uid: str
    kind: FindItemKind
    item_uid: str
    content: str
    spans: tuple[FindSpanResult, ...]
    source_context_name: str | None = None
    source_context_uid: str | None = None
    source_memory_uid: str | None = None


@dataclass(frozen=True, slots=True)
class FindResult:
    pattern: str
    context_names: tuple[str, ...]
    include_descendants: bool
    follow_embeds: bool
    mode: FindMode
    ignore_case: bool
    scanned_item_count: int
    occurrence_count: int
    matches: tuple[FindMatchResult, ...]


__all__ = [
    "FindItemKind",
    "FindMatchResult",
    "FindMode",
    "FindResult",
    "FindSpanResult",
]
