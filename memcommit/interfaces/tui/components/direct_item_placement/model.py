"""Operation-neutral state for one ordered direct-item insertion gap."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
)


@dataclass(frozen=True)
class DirectItemPreview:
    """The narrow item projection required by the placement component."""

    label: str
    content: str
    style: str
    source: SourceDisplayFacts


@dataclass(frozen=True)
class DirectItemPlacementRow:
    """One direct Context item shown beside its neighboring insertion gaps."""

    uid: str
    preview: DirectItemPreview

    def __post_init__(self) -> None:
        if not self.uid:
            raise ValueError("Direct-item placement rows require identity.")


@dataclass(frozen=True)
class DirectItemGap:
    """One exact gap in a frozen direct-item order."""

    position: int
    previous_uid: str | None
    next_uid: str | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
        ):
            raise ValueError("A direct-item gap requires a nonnegative position.")
        if self.position == 0 and self.previous_uid is not None:
            raise ValueError("The first direct-item gap cannot have a previous item.")


def _preview(item: Memory | MemoryRef | QueryContextRef | Context) -> DirectItemPreview:
    if isinstance(item, Memory):
        return DirectItemPreview(
            item.uid[:8],
            item.content,
            "memory-object",
            SourceDisplayFacts(form=SourceForm.MEMORY),
        )
    if isinstance(item, MemoryRef):
        return DirectItemPreview(
            item.uid[:8],
            (
                item.target.content
                if item.target is not None
                else f"{item.target_context_name}#{item.target_memory_uid[:8]}"
            ),
            "memory-object" if item.target is not None else "report-neutral",
            SourceDisplayFacts(
                form=SourceForm.MEMORY_REF,
                states=(
                    (SourceState.READ_ONLY,)
                    if item.target is not None
                    else (SourceState.DANGLING,)
                ),
            ),
        )
    if isinstance(item, QueryContextRef):
        return DirectItemPreview(
            item.uid[:8],
            item.name,
            "report-neutral",
            SourceDisplayFacts(form=SourceForm.QUERY_VIEW),
        )
    return DirectItemPreview(
        item.uid[:8],
        item.name,
        "report-neutral",
        SourceDisplayFacts(form=SourceForm.CONTEXT, reach=SourceReach.VIA_EMBED),
    )


def direct_item_placement_rows(context: Context) -> tuple[DirectItemPlacementRow, ...]:
    """Project every persisted direct-item slot without changing its order."""

    return tuple(
        DirectItemPlacementRow(uid=item.uid, preview=_preview(item))
        for item in context.iter_items()
    )


def direct_item_gap(
    rows: Sequence[DirectItemPlacementRow],
    position: int,
) -> DirectItemGap:
    """Freeze the exact neighbors around one insertion position."""

    values = tuple(rows)
    if (
        isinstance(position, bool)
        or not isinstance(position, int)
        or not 0 <= position <= len(values)
    ):
        raise ValueError(
            f"Direct-item insertion position must be between 0 and {len(values)}."
        )
    return DirectItemGap(
        position=position,
        previous_uid=values[position - 1].uid if position else None,
        next_uid=values[position].uid if position < len(values) else None,
    )


@dataclass
class DirectItemGapState:
    """Independent hover and retained selection for one ordered gap list."""

    rows: tuple[DirectItemPlacementRow, ...]
    cursor_position: int
    selected_position: int
    insertion_label: str = "INSERT HERE"

    @classmethod
    def create(
        cls,
        rows: Sequence[DirectItemPlacementRow],
        *,
        position: int | None = None,
        insertion_label: str = "INSERT HERE",
    ) -> "DirectItemGapState":
        values = tuple(rows)
        selected = len(values) if position is None else position
        direct_item_gap(values, selected)
        if not insertion_label.strip():
            raise ValueError("Insertion-gap controls require a visible action label.")
        return cls(values, selected, selected, insertion_label)

    @property
    def selected_gap(self) -> DirectItemGap:
        return direct_item_gap(self.rows, self.selected_position)

    def move(self, delta: int) -> bool:
        if delta not in {-1, 1}:
            raise ValueError("Insertion-gap movement must be -1 or 1.")
        candidate = max(0, min(self.cursor_position + delta, len(self.rows)))
        if candidate == self.cursor_position:
            return False
        self.cursor_position = candidate
        return True

    def choose_cursor(self) -> bool:
        changed = self.selected_position != self.cursor_position
        self.selected_position = self.cursor_position
        return changed

    def replace_rows(self, rows: Sequence[DirectItemPlacementRow]) -> None:
        """Reset a newly chosen Context to its explicit append gap."""

        self.rows = tuple(rows)
        self.cursor_position = len(self.rows)
        self.selected_position = len(self.rows)
