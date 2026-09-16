"""Reusable terminal frame and region components."""

from memcommit.adapters.console.terminal.components.frame.model import TuiRegion
from memcommit.adapters.console.terminal.components.frame.rendering import (
    bind_focused_frame_style,
    build_focused_frame,
    build_tui_frame,
    horizontal_rule,
)

__all__ = [
    "TuiRegion",
    "bind_focused_frame_style",
    "build_focused_frame",
    "build_tui_frame",
    "horizontal_rule",
]
