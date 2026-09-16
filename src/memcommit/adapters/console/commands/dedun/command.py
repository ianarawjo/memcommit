"""Run complete exact-plus-semantic DUN discovery and Apply as one operation."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.find_redundancies import (
    command as find_redundancies,
)
from memcommit.adapters.console.coordination.context_operand import (
    choose_context_operand,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text


def cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="CONTEXT",
            help="Context to dedun (defaults to current)",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to dedun (defaults to current)",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Dedun the exact Context root only (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Atomically Dedun each local lexical Context independently",
        ),
    ] = False,
) -> None:
    """Find and resolve complete DUN groups while preserving one existing UID."""

    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except ValueError as error:
        typer.secho(
            "Dedun error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    try:
        find_redundancies.run_dedun(
            context_name=context_name,
            evidence_json=False,
            include_descendants=preset is ContextScopePreset.RECURSIVE,
        )
    except typer.Exit:
        raise
    except Exception as error:
        typer.secho(
            "Dedun error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


__all__ = ["cmd"]
