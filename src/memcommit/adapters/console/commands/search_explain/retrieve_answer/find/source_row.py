"""Project deterministic Find matches as compact console Source rows."""

from __future__ import annotations

from memcommit.application.operations.search_explain.retrieve_answer.find.application import FindMatch
from memcommit.source_projection.model import SourceReferenceRow
from memcommit.source_projection.presentation import (
    SourceReferenceLayout,
    render_source_reference_row,
)


def find_reference_row(
    match: FindMatch,
    *,
    number: int,
) -> SourceReferenceRow:
    """Retain owner and optional MemoryRef Source identities in one compact row."""

    if not isinstance(match, FindMatch):
        raise TypeError("Find projection requires a FindMatch.")
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


def render_find_reference_row(
    match: FindMatch,
    *,
    number: int,
) -> str:
    """Render Find's identity/content/location arrangement from shared facts."""

    return render_source_reference_row(
        find_reference_row(match, number=number),
        layout=SourceReferenceLayout.IDENTITY_FIRST,
    )


__all__ = ["find_reference_row", "render_find_reference_row"]
