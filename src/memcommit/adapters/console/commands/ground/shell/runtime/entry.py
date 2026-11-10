"""Stable public entry point for the blank-Ground terminal runtime."""

from .terminal_interaction.workbench import (
    GROUND_CONTEXTS_FRAME_HEIGHT,
    GROUND_GOAL_FRAME_HEIGHT,
    _THINKING_INTERVAL_SECONDS,
    run_ground_shell,
)

__all__ = [
    "GROUND_CONTEXTS_FRAME_HEIGHT",
    "GROUND_GOAL_FRAME_HEIGHT",
    "_THINKING_INTERVAL_SECONDS",
    "run_ground_shell",
]
