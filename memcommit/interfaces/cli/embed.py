"""CLI composition and plain rendering for the Embed application use case."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.embed_application import (
    EmbedPlacement,
    EmbedRequest,
    EmbedResult,
    run_embed,
)
from memcommit.embed_runtime import MemoryStoreEmbedPort
from memcommit.interfaces.console.terminal import is_interactive_terminal
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.embed import choose_embed_setup
from memcommit.store import MemoryStore


def _interactive_terminal() -> bool:
    return is_interactive_terminal()


def _gap_description(placement: EmbedPlacement) -> str:
    if placement.previous_uid is not None and placement.next_uid is not None:
        return (
            f"between [{placement.previous_uid[:8]}] "
            f"and [{placement.next_uid[:8]}]"
        )
    if placement.next_uid is not None:
        return f"before [{placement.next_uid[:8]}] at the start"
    if placement.previous_uid is not None:
        return f"after [{placement.previous_uid[:8]}] at the end"
    return "as the only direct item"


def render_embed_plain(result: EmbedResult) -> None:
    """Render the established compact success line from a typed receipt."""

    typer.secho(
        f"Embedded '{display_escape_text(result.child_name)}' into "
        f"'{display_escape_text(result.into_name)}' "
        f"{_gap_description(result.placement)}.",
        fg=typer.colors.GREEN,
    )


def cmd(
    a: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Context to embed; omit with all options in a terminal to choose "
                "the Child, target, and insertion gap"
            )
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option("--into", help="Target Context whose direct order changes"),
    ] = None,
    before: Annotated[
        Optional[str],
        typer.Option(
            "--before",
            help="Insert before this direct item UID/prefix or exact pointer name",
        ),
    ] = None,
    after: Annotated[
        Optional[str],
        typer.Option(
            "--after",
            help="Insert after this direct item UID/prefix or exact pointer name",
        ),
    ] = None,
) -> None:
    if before is not None and after is not None:
        typer.secho(
            "Error: pass only one of --before or --after.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore()
    port = MemoryStoreEmbedPort.capture(store)
    frozen_plan = None
    if a is None:
        if into is not None or before is not None or after is not None:
            typer.secho(
                "Error: run 'mem embed' with no operands for interactive setup, "
                "or pass CHILD together with --into.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        if not _interactive_terminal():
            typer.secho(
                "Error: CHILD and --into are required outside a terminal; "
                "for example: mem embed CHILD --into CONTEXT.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            frozen_plan = choose_embed_setup(port)
        except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if frozen_plan is None:
            typer.echo("Embed cancelled — no Context was changed.")
            return
        request = frozen_plan.request
    else:
        if into is None:
            typer.secho(
                "Error: --into is required when CHILD is supplied.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        request = EmbedRequest(
            child_locator=a,
            into_locator=into,
            before=before,
            after=after,
        )

    try:
        result = run_embed(
            request,
            port=port,
            frozen_plan=frozen_plan,
        )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    render_embed_plain(result)
