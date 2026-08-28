"""Stable public surface for the split Ground command adapter."""

from __future__ import annotations

from memcommit.adapters.console.commands.ground.command.entrypoint import cmd
from memcommit.adapters.console.commands.ground.command import workflow as _workflow

__all__ = ["cmd"]


def __getattr__(name: str):
    """Preserve historical helper imports while workflow owns implementation."""

    try:
        return getattr(_workflow, name)
    except AttributeError as error:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from error


def __dir__() -> list[str]:
    return sorted({*globals(), *dir(_workflow)})
