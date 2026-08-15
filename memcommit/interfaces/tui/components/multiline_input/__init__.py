"""Shared writable multiline terminal input."""

from memcommit.interfaces.tui.components.multiline_input.component import (
    build_framed_multiline_input,
)
from memcommit.interfaces.tui.components.multiline_input.model import (
    FramedMultilineInput,
)

__all__ = [
    "FramedMultilineInput",
    "build_framed_multiline_input",
]
