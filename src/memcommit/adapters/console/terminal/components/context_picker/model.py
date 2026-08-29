"""Presentation values and typed receipts for the terminal Context picker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.core.context_targeting.model import (
    ContextSubtreeTarget,
    DirectMemoryTarget,
)
from memcommit.source_projection.model import SourceDisplayFacts
from memcommit.source_projection.presentation import SourceDisplayToken


@dataclass(frozen=True)
class ContextMemoryBadge:
    """One independently styled badge attached to a Memory preview row."""

    text: str
    style: str | None = None


@dataclass(frozen=True)
class ContextMemoryDetail:
    """One trusted key/value field for a focused nested picker row."""

    label: str
    value: str
    style: str | None = None


@dataclass(frozen=True)
class ContextMemoryRow:
    """One direct-item projection below a Context row."""

    label: str
    content: str
    style: Literal["memory-object", "report-neutral"] = "memory-object"
    selector: str | None = None
    source: SourceDisplayFacts | None = None
    object_label_override: str | None = None
    supplemental_annotations: tuple[SourceDisplayToken, ...] = ()
    annotation_style: str | None = None
    label_style: str | None = None
    badges: tuple[ContextMemoryBadge, ...] = ()
    section_label: str | None = None
    detail_title: str | None = None
    details: tuple[ContextMemoryDetail, ...] = ()


@dataclass(frozen=True)
class ContextPickerActionReceipt:
    """One in-place nested action projected through the picker footer."""

    label: str
    detail: str
    label_style: str = "class:memcommit.notification"
    detail_style: str = ""


@dataclass(frozen=True)
class ContextPickerNavigationUnit:
    """One viewport stop; callers explicitly opt nested rows into selection."""

    kind: Literal["CONTEXT", "MEMORY"]
    context_name: str
    memory_index: int | None = None


@dataclass(frozen=True)
class ContextPickerClipboardProjection:
    """One plain-text picker item or currently visible Context branch.

    ``memory_count`` remains the compatibility field name for the count of
    visible direct-item preview rows; those rows can now represent any durable
    direct-item form.
    """

    text: str
    scope: Literal["ITEM", "VISIBLE_BRANCH"]
    label: str
    context_count: int
    memory_count: int

    @property
    def item_count(self) -> int:
        return self.memory_count


# Compatibility spellings for established terminal callers. The receipts
# themselves are operation-neutral and owned by core Context targeting.
ContextMemorySelection = DirectMemoryTarget
ContextSubtreeSelection = ContextSubtreeTarget
