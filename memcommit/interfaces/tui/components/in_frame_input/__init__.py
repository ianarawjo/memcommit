"""Shared mechanics for attaching writable fields below a read pane."""

from memcommit.interfaces.tui.components.in_frame_input.inline_edit import (
    INLINE_AGENT_COMMENT_TITLE,
    INLINE_DIRECT_EDIT_TITLE,
    InlineEditSubmissionKind,
    build_inline_direct_edit_input,
    classify_inline_edit_submission,
)
from memcommit.interfaces.tui.components.in_frame_input.manager import (
    InFrameInputManager,
)
from memcommit.interfaces.tui.components.in_frame_input.model import (
    InFrameInputSection,
)

__all__ = [
    "INLINE_AGENT_COMMENT_TITLE",
    "INLINE_DIRECT_EDIT_TITLE",
    "InFrameInputManager",
    "InFrameInputSection",
    "InlineEditSubmissionKind",
    "build_inline_direct_edit_input",
    "classify_inline_edit_submission",
]
