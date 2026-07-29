"""Preview directional updates or unary semantic Context operations."""
from enum import Enum
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.atomize import AtomizeImpactError
from memcommit.commands.atomize_render import render_atomize_impact
from memcommit.commands.update_render import render_plan
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.update import UpdateError, plan_update


class ImpactOperation(str, Enum):
    """Unary operations supported by the impact preview command."""

    atomize = "atomize"


def _usage_error(message: str) -> None:
    typer.secho(f"Impact error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(2)


def _directional_impact(target_name: str) -> None:
    """Preserve the existing current-A to target-B impact behavior."""
    store = MemoryStore()
    try:
        source = store.load_current()
        target = store.load(target_name)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        typer.secho(f"Impact error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        session = plan_update(
            source,
            target,
            connect_codex_chatgpt_provider,
            status="impact",
        )
        store.save_impact_plan(session)
    except (OSError, QueryProviderError, UpdateError, ValueError) as error:
        typer.secho(f"Impact error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_plan(session, staged=False)


def _atomize_impact(
    *,
    context_name: str | None,
    show_all: bool,
) -> None:
    """Run the provisional direct-Memory atomization preview."""
    store = MemoryStore(create=False)
    try:
        ctx = (
            store.load_current_direct()
            if context_name is None
            else store.load_direct(context_name)
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(f"Impact error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        report = ops.impact_atomize(
            ctx,
            connect_codex_chatgpt_provider,
        )
    except (
        AtomizeImpactError,
        QueryProviderError,
        ValueError,
    ) as error:
        typer.secho(f"Impact error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_atomize_impact(report, show_all=show_all)


def cmd(
    operation: Annotated[
        Optional[ImpactOperation],
        typer.Argument(
            help="Optional unary impact operation: atomize",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Target Context B to assess from the current Context A",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context for a unary impact operation (defaults to current)",
        ),
    ] = None,
    show_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Include unchanged ATOMIC Memories in atomize output",
        ),
    ] = False,
) -> None:
    """Dispatch one of the two non-mutating impact preview forms."""
    if operation is ImpactOperation.atomize:
        if target_name is not None:
            _usage_error(
                "'atomize' cannot be combined with '--to'. "
                "Use either 'mem impact atomize' or "
                "'mem impact --to TARGET'."
            )
        _atomize_impact(
            context_name=context_name,
            show_all=show_all,
        )
        return

    if target_name is None:
        _usage_error(
            "choose a target with '--to TARGET' or preview atomization with "
            "'mem impact atomize'."
        )
    if context_name is not None or show_all:
        _usage_error(
            "'--context' and '--all' are only valid with "
            "'mem impact atomize'."
        )
    _directional_impact(target_name)
