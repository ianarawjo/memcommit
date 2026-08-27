"""Compatibility facade for console-owned progress feedback."""

from memcommit.adapters.interfaces.console.progress import (
    BUSY_FRAMES as BUSY_FRAMES,
    BUSY_INTERVAL_SECONDS as BUSY_INTERVAL_SECONDS,
    CommandProgress as CommandProgress,
    busy_suffix as busy_suffix,
    progressing_provider_factory as progressing_provider_factory,
    render_progress_line as render_progress_line,
)

__all__ = [
    "BUSY_FRAMES",
    "BUSY_INTERVAL_SECONDS",
    "CommandProgress",
    "busy_suffix",
    "progressing_provider_factory",
    "render_progress_line",
]
