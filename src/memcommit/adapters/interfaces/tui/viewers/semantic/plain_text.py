"""Plain-text projection for a typed Semantic Viewer document."""

from __future__ import annotations

from memcommit.adapters.console.tui.components.plain_text_clipboard import (
    plain_text_from_fragments,
)
from memcommit.adapters.interfaces.tui.viewers.semantic.model import SemanticViewerDocument


def semantic_document_plain_text(
    document: SemanticViewerDocument,
    *,
    focused_uid: str | None,
    whole_document: bool,
) -> str:
    """Project all sections or one exact focused section without UI chrome."""

    if not isinstance(document, SemanticViewerDocument):
        raise TypeError("Semantic plain-text projection requires a document.")
    if whole_document:
        fragments = tuple(
            fragment
            for section in document.sections
            for fragment in section.block.fragments
        )
    else:
        section = next(
            (section for section in document.sections if section.uid == focused_uid),
            document.sections[0] if document.sections else None,
        )
        fragments = () if section is None else section.block.fragments
    return plain_text_from_fragments(fragments, whole_document=True)


__all__ = ["semantic_document_plain_text"]
