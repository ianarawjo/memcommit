"""Stage a semantic update from current Context A to target Context B."""
from typing import Annotated

import typer

from memcommit.commands.update_render import render_plan
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.update import (
    UpdateError,
    plan_update,
    session_matches,
)


def cmd(
    target_name: Annotated[
        str,
        typer.Option(
            "--to",
            help="Target Context B to update from the current Context A",
        ),
    ],
    replace_stage: Annotated[
        bool,
        typer.Option(
            "--replace-stage",
            help="Replace a different or stale staged update",
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    try:
        source = store.load_current()
        target = store.load(target_name)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        existing = store.load_staged_update()
    except ValueError as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if existing is not None and not replace_stage:
        if session_matches(existing, source, target):
            render_plan(existing, staged=True)
            typer.echo("This update was already staged.")
            return
        typer.secho(
            "Update error: another or stale update is already staged. "
            "Review it before using '--replace-stage'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    cached = None
    try:
        cached = store.load_impact_plan()
    except ValueError:
        # A malformed read-only cache is never reused. A newly validated plan
        # replaces it only after provider success.
        cached = None

    try:
        if cached is not None and session_matches(cached, source, target):
            session = cached.with_status("staged")
        else:
            session = plan_update(
                source,
                target,
                connect_codex_chatgpt_provider,
                status="staged",
            )
        store.save_staged_update(session)
    except (OSError, QueryProviderError, UpdateError, ValueError) as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_plan(session, staged=True)
