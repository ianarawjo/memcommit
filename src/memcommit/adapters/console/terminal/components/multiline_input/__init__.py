"""Shared writable multiline terminal input."""

from memcommit.adapters.console.terminal.components.multiline_input.component import (
    build_framed_multiline_input,
)
from memcommit.adapters.console.terminal.components.multiline_input.model import (
    FramedMultilineInput,
)

__all__ = [
    "FramedMultilineInput",
    "build_framed_multiline_input",
]
