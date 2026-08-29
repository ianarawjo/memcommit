"""Stable public entry point for the blank-Ground terminal runtime."""

from .terminal_interaction.application import (
    GROUND_CONTEXTS_FRAME_HEIGHT,
    GROUND_GOAL_FRAME_HEIGHT,
    GROUND_LOCATION_FRAME_HEIGHT,
    INITIAL_QUESTION,
    _THINKING_INTERVAL_SECONDS,
    run_ground_shell,
)

__all__ = [
    "GROUND_CONTEXTS_FRAME_HEIGHT",
    "GROUND_GOAL_FRAME_HEIGHT",
    "GROUND_LOCATION_FRAME_HEIGHT",
    "INITIAL_QUESTION",
    "_THINKING_INTERVAL_SECONDS",
    "run_ground_shell",
]
