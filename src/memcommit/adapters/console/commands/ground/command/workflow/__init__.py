"""Ground command workflows split by user-visible responsibility."""

from __future__ import annotations

from . import apply as _apply
from . import create as _create
from . import edit as _edit
from . import inspect as _inspect
from . import open as _open
from .command import GroundCommandRequest, run_ground_command
from .inspect import render_ground_focus, render_ground_snapshot, render_ground_start
from .session import command as _session_command
from .session import dialogue as _session_dialogue
from .session import inspect as _session_inspect
from .session import review as _session_review

__all__ = [
    "GroundCommandRequest",
    "render_ground_focus",
    "render_ground_snapshot",
    "render_ground_start",
    "run_ground_command",
]

_COMPATIBILITY_OWNERS = (
    _apply,
    _create,
    _edit,
    _open,
    _inspect,
    _session_command,
    _session_dialogue,
    _session_inspect,
    _session_review,
)


def __getattr__(name: str):
    """Preserve historical helper lookup while each module owns behavior."""
    for module in _COMPATIBILITY_OWNERS:
        try:
            return getattr(module, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(
        {
            *globals(),
            *(name for module in _COMPATIBILITY_OWNERS for name in dir(module)),
        }
    )
