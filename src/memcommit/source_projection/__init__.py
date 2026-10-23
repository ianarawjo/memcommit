"""Shared semantic facts and display policy for readable source occurrences."""

from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReferenceRow,
    SourceReach,
    SourceState,
)
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceReferenceLayout,
    SourceTokenRole,
    render_source_reference_row,
    source_annotation_text,
    source_annotation_tokens,
    source_display_text,
    source_display_tokens,
    source_object_label,
    source_relationship_label,
)

__all__ = [
    "SourceDisplayFacts",
    "SourceDisplayToken",
    "SourceForm",
    "SourceReferenceRow",
    "SourceReferenceLayout",
    "SourceReach",
    "SourceState",
    "SourceTokenRole",
    "source_annotation_text",
    "source_annotation_tokens",
    "source_display_text",
    "source_display_tokens",
    "source_object_label",
    "source_relationship_label",
    "render_source_reference_row",
]
