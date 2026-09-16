"""CLI adapter for read-only Context and direct-item inspection."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.adapters.console.commands.show.presentation import render_show
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.show.application import (
    ShowDirectItemScopeError,
    ShowError,
)
from memcommit.application.operations.show.runtime import execute_show_cli_operand
from memcommit.persistence.store import MemoryStore


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Auto-typed existing Context, direct-item UID/prefix, or "
                "CONTEXT:UID; current embedded/query names remain accepted"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Parent context to inspect (defaults to current)",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Inspect only the selected Context or direct item",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help=("Include readable lexical descendants and embedded Contexts"),
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
        typer.secho(
            "Error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    include_recursive = preset is ContextScopePreset.RECURSIVE
    try:
        result = execute_show_cli_operand(
            selector,
            context_name=context_name,
            include_descendants=include_recursive,
            follow_embeds=include_recursive,
            store=MemoryStore(),
            allow_grants=True,
        )
    except ShowDirectItemScopeError as error:
        typer.secho(
            "Error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ShowError,
        ValueError,
    ) as error:
        typer.secho(
            "Error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    render_show(result)
