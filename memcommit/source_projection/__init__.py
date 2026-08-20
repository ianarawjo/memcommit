"""Shared semantic facts and display policy for readable source occurrences."""

from memcommit.source_projection.model import (
    SourceAccess,
    SourceDisplayFacts,
    SourceForm,
    SourceReferenceRow,
    SourceReach,
    SourceState,
    context_access_facts,
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
)

__all__ = [
    "SourceAccess",
    "SourceDisplayFacts",
    "SourceDisplayToken",
    "SourceForm",
    "SourceReferenceRow",
    "SourceReferenceLayout",
    "SourceReach",
    "SourceState",
    "SourceTokenRole",
    "context_access_facts",
    "source_annotation_text",
    "source_annotation_tokens",
    "source_display_text",
    "source_display_tokens",
    "source_object_label",
    "render_source_reference_row",
]
