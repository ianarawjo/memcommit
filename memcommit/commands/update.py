"""Apply a semantic update from current Context A to a local target Context B."""
from typing import Annotated

import typer

from memcommit.commands.update_render import render_plan
from memcommit.context_locator import resolve_context_locator
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.update import (
    UpdateError,
    applied_session_matches,
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
            help="Replace a different, stale, or applied update record",
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    try:
        current_name = store.current_context_name()
        if not current_name:
            raise RuntimeError("No current Context.")
        resolved_target_name = resolve_context_locator(
            target_name,
            current=current_name,
        )
        source = store.load(current_name)
        target = store.load(resolved_target_name)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        existing = store.load_staged_update()
    except ValueError as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if existing is not None and existing.status == "applied":
        if applied_session_matches(existing, source, target):
            render_plan(existing, applied=True)
            typer.echo("This update was already applied locally.")
            return
        if not replace_stage:
            typer.secho(
                "Update error: an applied update or its local working copy "
                "has diverged. Review it before using '--replace-stage'.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    if (
        existing is not None
        and existing.status == "impact"
        and not replace_stage
    ):
        typer.secho(
            "Update error: the active update record is not staged.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if (
        existing is not None
        and existing.status == "staged"
        and not replace_stage
    ):
        if session_matches(existing, source, target):
            session = existing
        else:
            typer.secho(
                "Update error: another or stale update is already staged. "
                "Review it before using '--replace-stage'.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
    else:
        session = None

    cached = None
    try:
        cached = store.load_impact_plan()
    except ValueError:
        # A malformed read-only cache is never reused. A newly validated plan
        # replaces it only after provider success.
        cached = None

    try:
        if session is None:
            if cached is not None and session_matches(cached, source, target):
                session = cached.with_status("staged")
            else:
                session = plan_update(
                    source,
                    target,
                    connect_codex_chatgpt_provider,
                    status="staged",
                )
            # Bind the staged intent to the active record observed above.
            # This prevents two update processes from silently replacing one
            # another between planning and local application.
            store.save_staged_update(
                session,
                expected_current=existing,
            )
        applied = store.apply_staged_update(session)
    except (
        OSError,
        QueryProviderError,
        RuntimeError,
        UpdateError,
        ValueError,
    ) as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_plan(applied, applied=True)
