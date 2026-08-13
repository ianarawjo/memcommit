"""Compatibility helpers for rendering semantic Viewer blocks."""

from __future__ import annotations

from memcommit.interfaces.tui.viewers.semantic.model import (
    SemanticViewerBlock,
    ViewerAnchor,
    ViewerFragments,
)


_RESTING_STYLE = {
    "class:viewer-section": "class:section",
    "class:report-label.focused": "class:report-label",
    "class:viewer-body.focused": "class:viewer-body",
    "class:detail-card.focused": "class:detail-card",
    "class:memory-object.focused": "class:memory-object",
    "class:impact.keep.focused": "class:impact.keep",
    "class:impact.redact.focused": "class:impact.redact",
    "class:impact.summarize.focused": "class:impact.summarize",
    "class:impact.reframe.focused": "class:impact.reframe",
    "class:impact.forget.focused": "class:impact.forget",
    "class:impact.custom.focused": "class:impact.custom",
    "class:impact.other.focused": "class:impact.other",
    "class:impact.edit.focused": "class:impact.edit",
    "class:impact.add.focused": "class:impact.add",
    "class:impact.remove.focused": "class:impact.remove",
    "class:option-card.focused": "class:option-card",
    "class:option-card.other": "class:option-card",
    "class:choice": "",
}


def semantic_viewer_block_fragments(
    fragments: ViewerFragments,
    *,
    active: bool,
    viewer_focused: bool = True,
    anchor: ViewerAnchor = "start",
    focus_indices: tuple[int, ...] | None = None,
) -> list[tuple[str, str]]:
    return SemanticViewerBlock(
        tuple(fragments),
        anchor=anchor,
        focus_indices=focus_indices,
    ).render(active=active, viewer_focused=viewer_focused)


def deactivate_semantic_viewer_fragments(
    fragments: ViewerFragments,
) -> list[tuple[str, str]]:
    return [(_RESTING_STYLE.get(style, style), text) for style, text in fragments]
