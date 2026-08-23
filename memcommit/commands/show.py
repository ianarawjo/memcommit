"""CLI adapter for read-only Context and direct-item inspection."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.interfaces.cli.show import render_show
from memcommit.interfaces.console.text import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.show_application import ShowError, ShowRequest
from memcommit.show_runtime import execute_show
from memcommit.store import MemoryStore


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help="Item UID/prefix or exact embedded-context name; omit to show the whole context"
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
    if include_recursive and selector is not None:
        typer.secho(
            "Error: --recursive/-r cannot be combined with a direct-item "
            "selector; omit SELECTOR and choose the root with --context/-c.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    try:
        result = execute_show(
            ShowRequest(
                context_name=context_name,
                selector=selector,
                include_descendants=include_recursive,
                follow_embeds=include_recursive,
            ),
            store=MemoryStore(),
            allow_grants=True,
        )
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
