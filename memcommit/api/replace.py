"""Stable public values for deterministic Replace planning and Apply."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ReplaceMode = Literal["LITERAL", "REGEX"]


@dataclass(frozen=True, slots=True)
class ReplaceSpanResult:
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class ReplaceMemoryPlanResult:
    memory_uid: str
    before_content: str
    after_content: str
    changed: bool
    spans: tuple[ReplaceSpanResult, ...]


@dataclass(frozen=True, slots=True)
class ReplaceContextPlanResult:
    context_name: str
    context_uid: str
    context_digest: str
    scanned_memory_count: int
    matches: tuple[ReplaceMemoryPlanResult, ...]


@dataclass(frozen=True, slots=True)
class ReplacePlanResult:
    pattern: str
    replacement: str
    context_names: tuple[str, ...]
    include_descendants: bool
    follow_embeds: bool
    mode: ReplaceMode
    ignore_case: bool
    plan_digest: str
    scanned_context_count: int
    scanned_memory_count: int
    matched_memory_count: int
    changed_memory_count: int
    occurrence_count: int
    contexts: tuple[ReplaceContextPlanResult, ...]
    _handle: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ReplaceCheckpointResult:
    context_name: str
    context_uid: str
    checkpoint_uid: str


@dataclass(frozen=True, slots=True)
class ReplaceApplyReceipt:
    plan_digest: str
    applied: bool
    scanned_context_count: int
    scanned_memory_count: int
    matched_memory_count: int
    changed_memory_count: int
    occurrence_count: int
    checkpoints: tuple[ReplaceCheckpointResult, ...]


__all__ = [
    "ReplaceApplyReceipt",
    "ReplaceCheckpointResult",
    "ReplaceContextPlanResult",
    "ReplaceMemoryPlanResult",
    "ReplaceMode",
    "ReplacePlanResult",
    "ReplaceSpanResult",
]
