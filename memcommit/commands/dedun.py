"""Run complete exact-plus-semantic DUN discovery and Apply as one operation."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands import consolidate, find_duplicates
from memcommit.commands.context_operand import choose_context_operand
from memcommit.interfaces.console.text import display_escape_text


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
    evidence_json: Annotated[
        bool,
        typer.Option("--evidence-json", hidden=True),
    ] = False,
    evidence: Annotated[
        Optional[list[str]],
        typer.Option("--evidence", hidden=True),
    ] = None,
    survivors: Annotated[
        Optional[list[str]],
        typer.Option("--survivor", hidden=True),
    ] = None,
    expected_revision: Annotated[
        Optional[str],
        typer.Option("--expected-revision", hidden=True),
    ] = None,
    apply_now: Annotated[
        bool,
        typer.Option("--apply", hidden=True),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option("--plain", hidden=True),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", hidden=True),
    ] = False,
) -> None:
    """Find and resolve complete DUN groups while preserving one existing UID."""

    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
    except ValueError as error:
        typer.secho(
            "Dedun error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    replay_requested = bool(
        evidence
        or survivors
        or expected_revision is not None
        or apply_now
        or plain
        or tui
    )
    if replay_requested:
        if context_name is not None or evidence_json:
            typer.secho(
                "Dedun error: discovery options cannot be combined with an exact "
                "review replay.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        consolidate.cmd(
            evidence=evidence,
            survivors=survivors,
            expected_revision=expected_revision,
            apply_now=apply_now,
            plain=plain,
            tui=tui,
        )
        return
    try:
        find_duplicates.run_dedun(
            context_name=context_name,
            evidence_json=evidence_json,
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
