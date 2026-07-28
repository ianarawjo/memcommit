"""Preview the semantic impact of current Context A on target Context B."""
from typing import Annotated

import typer

from memcommit.commands.update_render import render_plan
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.update import UpdateError, plan_update


def cmd(
    target_name: Annotated[
        str,
        typer.Option(
            "--to",
            help="Target Context B to assess from the current Context A",
        ),
    ],
) -> None:
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
