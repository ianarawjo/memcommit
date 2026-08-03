"""Initialize one Study as a complete copy of an editable baseline Profile."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import (
    ProfileError,
    STUDY_BASELINE_PROFILE_NAME,
    init_study_profile,
)


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(help=("New Profile name; omit for a timestamped unique name")),
    ] = None,
    baseline_profile: Annotated[
        str,
        typer.Option(
            "--from-profile",
            help=("Editable source Profile whose complete topology will be copied"),
        ),
    ] = STUDY_BASELINE_PROFILE_NAME,
) -> None:
    """Clone one live Study baseline into one ordinary Profile."""

    try:
        result = init_study_profile(baseline_profile, name=name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Initialized Study Profile '{display_escape_text(result.profile.name)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo("Baseline Profile: " + display_escape_text(result.baseline_profile_name))
    current = (
        display_escape_text(result.inspection.current_context)
        if result.inspection.current_context
        else "(none)"
    )
    typer.echo(
        f"Contexts {len(result.inspection.context_names)} · "
        f"Memories {result.inspection.ordinary_memory_count} · current={current}"
    )
    typer.echo("The complete baseline Context topology was copied without splitting.")
    typer.echo(
        "Operational history starts empty; checkpoints, sessions, caches, locks, "
        "and run logs were not imported."
    )
    typer.echo(
        "Active Profile unchanged: " + display_escape_text(result.active_profile_name)
    )
    typer.echo("Use it with: mem profile " + display_escape_text(result.profile.name))
