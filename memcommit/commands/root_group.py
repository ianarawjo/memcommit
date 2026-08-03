"""Root Click routing shared by every top-level ``mem`` command."""
from __future__ import annotations

from typing import Any

try:  # Typer 0.27+ vendors Click; older supported Typer releases do not.
    from typer import _click as click
except ImportError:  # pragma: no cover - compatibility with older Typer
    import click
from typer.core import TyperGroup

from memcommit.write_protection import (
    WriteProtectionError,
    WriteProtectionRegistryError,
)


class MemCommandGroup(TyperGroup):
    """Render store-level protection failures without Python tracebacks.

    Protection is enforced below individual commands, including legacy and
    semantic writers.  Converting only these typed failures at the root keeps
    every mutation path consistent without teaching the persistence layer
    about Click or relying on each command to remember a local catch block.
    """

    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except (WriteProtectionError, WriteProtectionRegistryError) as error:
            raise click.ClickException(str(error)) from error
