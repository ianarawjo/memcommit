"""Shared deterministic activity animation for terminal interfaces."""

from __future__ import annotations


BUSY_FRAMES = (".", "..", "…")
BUSY_INTERVAL_SECONDS = 0.35


def busy_suffix(frame_index: int) -> str:
    """Return the shared deterministic dot-animation frame."""

    return BUSY_FRAMES[frame_index % len(BUSY_FRAMES)]


__all__ = ["BUSY_FRAMES", "BUSY_INTERVAL_SECONDS", "busy_suffix"]
