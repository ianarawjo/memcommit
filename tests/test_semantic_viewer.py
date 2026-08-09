from __future__ import annotations

import pytest

from memcommit.commands.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
    deactivate_semantic_viewer_fragments,
    semantic_viewer_block_fragments,
)


def test_focus_styles_only_semantic_identity_and_anchors_complete_block():
    fragments = semantic_viewer_block_fragments(
        [
            ("class:block-heading", " CLASSIFICATION\n"),
            ("", " Explanatory prose stays neutral.\n"),
            ("class:memory-object", " [1] One Memory\n"),
        ],
        active=True,
        anchor="both",
    )

    assert fragments == [
        ("[SetCursorPosition]", ""),
        ("class:viewer-section", " CLASSIFICATION\n"),
        ("", " Explanatory prose stays neutral.\n"),
        ("class:memory-object.focused", " [1] One Memory\n"),
        ("[SetCursorPosition]", ""),
    ]


def test_inactive_viewer_keeps_content_and_durable_selection_without_focus():
    fragments = deactivate_semantic_viewer_fragments(
        [
            ("[SetCursorPosition]", ""),
            ("class:viewer-section", "WHAT MEM UNDERSTOOD"),
            ("class:detail-card.focused", "Focused card heading"),
            ("class:memory-object.focused", "Focused Memory"),
            ("class:option-card.focused", "Option cursor"),
            ("class:option-card.selected", "Durable choice"),
        ]
    )

    assert fragments == [
        ("[SetCursorPosition]", ""),
        ("class:section", "WHAT MEM UNDERSTOOD"),
        ("class:detail-card", "Focused card heading"),
        ("class:memory-object", "Focused Memory"),
        ("class:option-card", "Option cursor"),
        ("class:option-card.selected", "Durable choice"),
    ]


def test_unfocused_block_never_adds_a_viewport_anchor():
    fragments = semantic_viewer_block_fragments(
        [("class:section", "WHAT HAPPENED")],
        active=True,
        viewer_focused=False,
    )

    assert fragments == [("class:section", "WHAT HAPPENED")]


def test_focus_indices_restrict_card_emphasis_to_its_identity_line():
    fragments = semantic_viewer_block_fragments(
        [
            ("class:detail-card", "╭─ TITLE ─╮\n"),
            ("class:detail-card", "│ body    │\n"),
            ("class:detail-card", "╰─────────╯\n"),
        ],
        active=True,
        anchor="end",
        focus_indices=(0,),
    )

    assert fragments == [
        ("class:detail-card.focused", "╭─ TITLE ─╮\n"),
        ("class:detail-card", "│ body    │\n"),
        ("class:detail-card", "╰─────────╯\n"),
        ("[SetCursorPosition]", ""),
    ]


def test_focus_indices_are_validated():
    with pytest.raises(ValueError, match="out of range"):
        SemanticViewerBlock(
            (("class:section", "TITLE"),),
            focus_indices=(1,),
        )


def test_document_derives_navigation_and_rendering_from_same_section_order():
    document = SemanticViewerDocument(
        (
            SemanticViewerSection(
                "REPORT:UNDERSTANDING",
                "UNDERSTANDING",
                SemanticViewerBlock((("class:section", "UNDERSTOOD\n"),)),
            ),
            SemanticViewerSection(
                "REPORT:RESULTS",
                "RESULTS",
                SemanticViewerBlock((("class:section", "RESULTS"),)),
            ),
        )
    )

    assert [section.uid for section in document.navigation_sections] == [
        "REPORT:UNDERSTANDING",
        "REPORT:RESULTS",
    ]
    rendered = document.render(focused_uid="REPORT:RESULTS")
    assert rendered == [
        ("class:section", "UNDERSTOOD\n"),
        ("[SetCursorPosition]", ""),
        ("class:viewer-section", "RESULTS"),
    ]


def test_document_rejects_duplicate_section_identities():
    section = SemanticViewerSection(
        "REPORT:SAME",
        "REPORT",
        SemanticViewerBlock((("class:section", "Same"),)),
    )

    with pytest.raises(ValueError, match="unique"):
        SemanticViewerDocument((section, section))
