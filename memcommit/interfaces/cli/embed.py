"""CLI composition and plain rendering for the Embed application use case."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.context_targeting.loading import (
    resolve_local_direct_memory_locator,
)
from memcommit.context_targeting.model import DirectMemoryLocator
from memcommit.context_targeting.operands import choose_endpoint_operand
from memcommit.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
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
            help=(
                "Source Context when ITEM is omitted; otherwise the owner "
                "Context for an explicit Memory selector"
            ),
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
    try:
        target_option = choose_endpoint_operand(
            None,
            role="Target",
            options=(("--into", into), ("--to", to)),
        )
    except ValueError as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

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
    source_from_option = a is None and source_name is not None
    source_item = source_name if source_from_option else a
    memory_owner = None if source_from_option else source_name
    if source_item is None:
        if (
            target_option is not None
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
            parsed_source = (
                parse_auto_typed_context_memory_operand(
                    source_item,
                    explicit_memory_context=memory_owner,
                )
                if not source_from_option
                else None
            )
            if isinstance(parsed_source, DirectMemoryLocator):
                memory_target = resolve_local_direct_memory_locator(
                    port.store,
                    source_item,
                    current=port.current_context_name,
                    explicit_context=memory_owner,
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
                    child_locator=source_item,
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
