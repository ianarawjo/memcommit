"""Reusable terminal frame styling and vertical composition."""

from memcommit.adapters.console.terminal.components.frame.rendering import (
    bind_focused_frame_style,
    build_focused_frame,
    build_tui_frame,
    horizontal_rule,
)

__all__ = [
    "bind_focused_frame_style",
    "build_focused_frame",
    "build_tui_frame",
    "horizontal_rule",
]
