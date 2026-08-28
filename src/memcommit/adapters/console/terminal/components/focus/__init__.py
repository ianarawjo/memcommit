"""Shared keyboard-surface focus model and controller."""

from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
    focus_in_order,
)

__all__ = [
    "FocusSurface",
    "SurfaceActionResult",
    "SurfaceFocusController",
    "SurfaceMoveResult",
    "bind_surface_navigation",
    "focus_in_order",
]
