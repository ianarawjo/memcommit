"""Initialize one repeatable Study as three isolated Task Profiles."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import (
    ProfileError,
    default_study_bundle_root,
    init_study_profiles,
)


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(help="Portable Study name; omit for a timestamped unique name"),
    ] = None,
    source: Annotated[
        Optional[Path],
        typer.Option(
            "--from",
            help=(
                "Directory containing task-1, task-2, and task-3 packages; "
                "defaults to this checkout's generated bundles"
            ),
        ),
    ] = None,
) -> None:
    """Create one Study whose three tasks share a frozen baseline receipt."""

    try:
        result = init_study_profiles(source or default_study_bundle_root(), name=name)
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
    typer.echo("Profiles:")
    for task, profile, inspection in zip(
        (1, 2, 3), result.profiles, result.inspections, strict=True
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
    typer.echo(
        "Operational history starts empty; bundle checkpoints and sessions "
        "were not imported."
    )
    typer.echo("Active Profile unchanged: " + display_escape_text(result.active_profile_name))
    typer.echo("Use Task 1 with: mem profile " + display_escape_text(result.profiles[0].name))
