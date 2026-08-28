"""Shared pane-local direct-edit convention."""

from __future__ import annotations

from typing import Literal

from prompt_toolkit.layout import AnyDimension, Dimension

from memcommit.adapters.console.tui.components.multiline_input import (
    FramedMultilineInput,
    build_framed_multiline_input,
)


InlineEditSubmissionKind = Literal["NOOP", "DIRECT", "COMMENT", "BOTH"]

INLINE_DIRECT_EDIT_TITLE = "EDIT (DIRECTLY)"
INLINE_AGENT_COMMENT_TITLE = "COMMENT (FOR THE AGENT)"


def build_inline_direct_edit_input(
    *,
    text: str = "",
    buffer_name: str | None = None,
    height: AnyDimension = None,
) -> FramedMultilineInput:
    """Build the exact-text half of a pane-local edit/comment exchange."""

    return build_framed_multiline_input(
        INLINE_DIRECT_EDIT_TITLE,
        text=text,
        prompt="> ",
        buffer_name=buffer_name,
        height=(height if height is not None else Dimension(min=3, preferred=3, max=4)),
    )


def classify_inline_edit_submission(
    *,
    original: str,
    edited: str,
    comment: str,
) -> InlineEditSubmissionKind:
    """Classify one pane-local exchange without inferring user intent."""

    direct = edited != original
    agent_comment = bool(comment.strip())
    if direct and agent_comment:
        return "BOTH"
    if direct:
        return "DIRECT"
    if agent_comment:
        return "COMMENT"
    return "NOOP"
