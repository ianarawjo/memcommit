"""Initialize one Study as task Profiles plus switchable authority Profiles."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import (
    ProfileError,
    STUDY_BASELINE_PROFILE_NAME,
    init_study_profiles,
)


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=("Portable Study name; omit for a timestamped unique name")
        ),
    ] = None,
    baseline_profile: Annotated[
        str,
        typer.Option(
            "--from-profile",
            help=(
                "Editable source Profile containing task-1, task-2, task-3, "
                "and granted-memory branches"
            ),
        ),
    ] = STUDY_BASELINE_PROFILE_NAME,
) -> None:
    """Clone one live Study baseline into isolated task and authority Profiles."""

    try:
        result = init_study_profiles(baseline_profile, name=name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Initialized Study '{display_escape_text(result.name)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Created: {display_escape_text(result.created_at)}")
    typer.echo(f"Study UID: {result.uid}")
    typer.echo("Baseline Profile: " + display_escape_text(baseline_profile))
    typer.echo("Profiles:")
    for task, profile, inspection in zip(
        (1, 2, 3),
        result.profiles,
        result.inspections,
        strict=True,
    ):
        current = (
            display_escape_text(inspection.current_context)
            if inspection.current_context
            else "(none)"
        )
        typer.echo(
            f"  Task {task} · {display_escape_text(profile.name)} · "
            f"{len(inspection.context_names)} Contexts · "
            f"{inspection.ordinary_memory_count} Memories · current={current}"
        )
    if result.support_profiles:
        typer.echo("Authority Profiles:")
        for task, profile, inspection in zip(
            (1, 2, 3),
            result.support_profiles,
            result.support_inspections,
            strict=True,
        ):
            current = (
                display_escape_text(inspection.current_context)
                if inspection.current_context
                else "(none)"
            )
            typer.echo(
                f"  Authority {task} · {display_escape_text(profile.name)} · "
                f"{len(inspection.context_names)} Contexts · "
                f"{inspection.ordinary_memory_count} Memories · current={current}"
            )
        typer.echo("All task and authority Profiles are available to normal selection.")
    typer.echo(
        "Operational history starts empty; bundle checkpoints and sessions "
        "were not imported."
    )
    typer.echo(
        "Active Profile unchanged: " + display_escape_text(result.active_profile_name)
    )
    typer.echo(
        "Use Task 1 with: mem profile " + display_escape_text(result.profiles[0].name)
    )
