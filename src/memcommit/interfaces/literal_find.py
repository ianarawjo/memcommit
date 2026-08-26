"""Terminal-independent projection of literal Find matches as Source rows."""

from __future__ import annotations

from memcommit.operations.find.literal_application import LiteralFindMatch
from memcommit.source_projection.model import SourceReferenceRow
from memcommit.source_projection.presentation import (
    SourceReferenceLayout,
    render_source_reference_row,
)


def literal_find_reference_row(
    match: LiteralFindMatch,
    *,
    number: int,
) -> SourceReferenceRow:
    """Retain owner and optional MemoryRef Source identities in one compact row."""

    if not isinstance(match, LiteralFindMatch):
        raise TypeError("Literal Find projection requires a LiteralFindMatch.")
    source = match.source
    return SourceReferenceRow(
        number=number,
        content=source.content,
        uid=source.item_uid,
        context_name=source.context_name,
        alias=f"m{source.source_position}",
        source_uid=source.source_memory_uid,
        source_context_name=source.source_context_name,
    )


def render_literal_find_reference_row(
    match: LiteralFindMatch,
    *,
    number: int,
) -> str:
    """Render Find's identity/content/location arrangement from shared facts."""

    return render_source_reference_row(
        literal_find_reference_row(match, number=number),
        layout=SourceReferenceLayout.IDENTITY_FIRST,
    )


__all__ = ["literal_find_reference_row", "render_literal_find_reference_row"]
