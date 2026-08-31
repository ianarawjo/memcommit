"""User-facing Unlock command and compatibility resource routes."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.coordination.write_protection import (
    ProtectionCommandGroup,
    change_auto_target_protection,
    change_context_protection,
    change_default_protection,
    change_memory_protection,
    change_profile_protection,
    recursive_scope,
)


app = typer.Typer(
    cls=ProtectionCommandGroup,
    no_args_is_help=False,
    invoke_without_command=True,
    help=(
        "Remove protection from the current Context or an auto-typed "
        "Context/Memory target; use --profile for the active Profile."
    ),
)


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Explicit Context target, or owner when --memory is supplied",
        ),
    ] = None,
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            metavar="[CONTEXT:]UID_OR_PREFIX",
            help="Explicit direct Memory target; accepts a short prefix",
        ),
    ] = None,
    profile: Annotated[
        bool,
        typer.Option("--profile", help="Unlock the active Profile"),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Unlock only the selected Context"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also unlock existing descendants of a Context target",
        ),
    ] = False,
) -> None:
    """Unlock the current Context or an explicitly typed option target."""
    if ctx.invoked_subcommand is None:
        change_default_protection(
            protected=False,
            context_name=context_name,
            memory_selector=memory_selector,
            profile=profile,
            direct=direct,
            recursive=recursive,
        )
    elif context_name is not None or memory_selector is not None or profile:
        raise typer.BadParameter(
            "Top-level --context, --memory, and --profile cannot be combined "
            "with a compatibility resource command."
        )
    elif (direct or recursive) and ctx.invoked_subcommand not in {
        "context",
        ProtectionCommandGroup.AUTO_TARGET_COMMAND,
    }:
        raise typer.BadParameter(
            "Context scope flags apply only to the current or an explicit "
            "Context target."
        )


@app.command(ProtectionCommandGroup.AUTO_TARGET_COMMAND, hidden=True)
def target(
    ctx: typer.Context,
    target: Annotated[
        str,
        typer.Argument(help="Existing Context locator, Memory UID/prefix, or CONTEXT:UID"),
    ],
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Unlock only a Context target"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also unlock existing lexical descendants of a Context target",
        ),
    ] = False,
) -> None:
    """Unlock one auto-typed Context or direct Memory target."""
    change_auto_target_protection(
        target,
        protected=False,
        direct=direct or bool(ctx.parent and ctx.parent.params.get("direct")),
        recursive=recursive or bool(ctx.parent and ctx.parent.params.get("recursive")),
    )


@app.command("context")
def context(
    ctx: typer.Context,
    context_name: Annotated[
        Optional[str],
        typer.Argument(help="Existing ordinary Context (defaults to current Context)"),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Unlock only the selected Context"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also unlock existing lexical descendants atomically",
        ),
    ] = False,
) -> None:
    """Allow changes to a previously protected Context."""
    change_context_protection(
        context_name,
        protected=False,
        recursive=recursive_scope(
            direct=direct or bool(ctx.parent and ctx.parent.params.get("direct")),
            recursive=recursive or bool(ctx.parent and ctx.parent.params.get("recursive")),
        ),
    )


@app.command("profile")
def profile() -> None:
    """Allow Profile writes, preserving narrower Context/Memory locks."""
    change_profile_protection(protected=False)


@app.command("memory")
def memory(
    selector: Annotated[
        str,
        typer.Argument(help="UID or unambiguous prefix of a directly owned Memory"),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Existing ordinary Context (defaults to current Context)",
        ),
    ] = None,
) -> None:
    """Allow editing or removing one protected direct Memory occurrence."""
    change_memory_protection(selector, context_name, protected=False)


__all__ = ["app"]
