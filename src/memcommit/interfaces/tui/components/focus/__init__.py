"""Shared keyboard-surface focus model and controller."""

from memcommit.interfaces.tui.components.focus.controller import (
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
