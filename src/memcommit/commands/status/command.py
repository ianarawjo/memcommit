"""CLI adapter for the read-only Status application."""

from __future__ import annotations

from typing import Annotated

import typer

from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.adapters.interfaces.cli.status import render_status
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.status.application import (
    NoCurrentStatusContextError,
    StatusError,
    StatusRequest,
)
from memcommit.application.operations.status.runtime import execute_status
from memcommit.persistence.store import MemoryStore


def cmd(
    short: Annotated[
        bool,
        typer.Option(
            "-s",
            "--short",
            help="Show orientation and item counts on one line",
        ),
    ] = False,
    branch: Annotated[
        bool,
        typer.Option(
            "-b",
            "--branch",
            help="Include the active Profile and Context lineage",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Inspect only the current Context",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help=(
                "Include readable lexical descendants and embedded Contexts "
                "in inventory totals"
            ),
        ),
    ] = False,
) -> None:
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except ValueError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    include_recursive = preset is ContextScopePreset.RECURSIVE
    try:
        result = execute_status(
            StatusRequest(
                include_descendants=include_recursive,
                follow_embeds=include_recursive,
            ),
            store=MemoryStore(),
        )
    except NoCurrentStatusContextError as error:
        # Preserve Status as a non-failing shell orientation probe when the
        # active Store has not selected its first Context yet.
        typer.secho(str(error), fg=typer.colors.YELLOW)
        return
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        StatusError,
        ValueError,
    ) as error:
        typer.secho(f"Status error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    render_status(result, short=short, branch=branch)


__all__ = ["cmd"]
