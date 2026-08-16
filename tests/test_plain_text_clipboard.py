"""Shared semantic plain-text projection contracts."""

from memcommit.interfaces.tui.components.plain_text_clipboard import (
    plain_text_from_fragments,
)
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
    semantic_document_plain_text,
)


def test_fragment_projection_preserves_complete_and_anchored_ranges():
    fragments = (
        ("class:title", "Before\n"),
        ("[SetCursorPosition]", ""),
        ("class:memory-object", "Focused\nunit\n"),
        ("[SetCursorPosition]", ""),
        ("class:viewer-body", "After\n"),
    )

    assert plain_text_from_fragments(
        fragments,
        whole_document=True,
    ) == "Before\nFocused\nunit\nAfter"
    assert plain_text_from_fragments(
        fragments,
        whole_document=False,
    ) == "Focused\nunit"


def test_single_anchor_projection_falls_back_to_its_visual_line():
    assert plain_text_from_fragments(
        (
            ("class:title", "Before\n"),
            ("[SetCursorPosition]", ""),
            ("class:viewer-body", "Focused line\nAfter\n"),
        ),
        whole_document=False,
    ) == "Focused line"


def test_semantic_document_projection_uses_exact_section_identity():
    document = SemanticViewerDocument(
        (
            SemanticViewerSection(
                "first",
                "REPORT",
                SemanticViewerBlock((("class:title", "First\n"),)),
            ),
            SemanticViewerSection(
                "second",
                "MEMORY",
                SemanticViewerBlock(
                    (("class:memory-object", "Second\ncontinued\n"),)
                ),
            ),
        )
    )

    assert semantic_document_plain_text(
        document,
        focused_uid="second",
        whole_document=False,
    ) == "Second\ncontinued"
    assert semantic_document_plain_text(
        document,
        focused_uid="second",
        whole_document=True,
    ) == "First\nSecond\ncontinued"
