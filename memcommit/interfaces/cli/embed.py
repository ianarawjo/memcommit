"""CLI composition and plain rendering for the Embed application use case."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.context_targeting.loading import (
    resolve_local_direct_memory_locator,
)
from memcommit.context_targeting.resolution import (
    is_direct_memory_locator_operand,
)
from memcommit.embed_application import (
    EmbedPlacement,
    EmbedRequest,
    EmbedResult,
    FrozenMemoryEmbedPlan,
    MemoryEmbedRequest,
    MemoryEmbedResult,
    run_embed,
    run_memory_embed,
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


def render_embed_plain(result: EmbedResult | MemoryEmbedResult) -> None:
    """Render the established compact success line from a typed receipt."""

    if isinstance(result, MemoryEmbedResult):
        typer.secho(
            f"Embedded Memory [{result.memory_uid[:8]}] from "
            f"'{display_escape_text(result.source_name)}' as "
            f"[{result.embed_uid[:8]}] in "
            f"'{display_escape_text(result.into_name)}' "
            f"{_gap_description(result.placement)}.",
            fg=typer.colors.GREEN,
        )
        return
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
                "Context, unique local Memory UID/prefix, or CONTEXT:UID; "
                "omit with all options in a terminal for interactive setup"
            )
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Compatibility Source Context for an explicit Memory selector",
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help="Target Context whose direct order changes (defaults to current)",
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Compatibility alias for --into",
        ),
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
    if into is not None and to is not None:
        typer.secho(
            "Error: use only one of --into or --to.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    # Resolve spelling ambiguity before capturing even the current Context:
    # a mutating command must never inherit Click's silent last-option-wins rule.
    target_option = into or to

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
        if (
            source_name is not None
            or into is not None
            or to is not None
            or before is not None
            or after is not None
        ):
            typer.secho(
                "Error: run 'mem embed' with no operands for interactive setup, "
                "or pass an item for the non-interactive form.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        if not _interactive_terminal():
            typer.secho(
                "Error: an item is required outside a terminal; for example: "
                "mem embed CHILD, mem embed MEMORY, or mem embed CONTEXT:MEMORY. "
                "Pass --into to override the current Target Context.",
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
        target_locator = target_option or port.current_context_name
        if target_locator is None:
            typer.secho(
                "Error: no current Context. Pass --into (or --to) or initialize "
                "a Context first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            if is_direct_memory_locator_operand(
                a,
                explicit_context=source_name,
            ):
                memory_target = resolve_local_direct_memory_locator(
                    port.store,
                    a,
                    current=port.current_context_name,
                    explicit_context=source_name,
                )
                request = MemoryEmbedRequest(
                    memory_selector=memory_target.memory_uid,
                    source_locator=memory_target.context_name,
                    into_locator=target_locator,
                    before=before,
                    after=after,
                )
            else:
                request = EmbedRequest(
                    child_locator=a,
                    into_locator=target_locator,
                    before=before,
                    after=after,
                )
        except (FileNotFoundError, OSError, TypeError, ValueError) as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    try:
        if isinstance(request, MemoryEmbedRequest):
            result = run_memory_embed(
                request,
                port=port,
                frozen_plan=(
                    frozen_plan
                    if isinstance(frozen_plan, FrozenMemoryEmbedPlan)
                    else None
                ),
            )
        else:
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
