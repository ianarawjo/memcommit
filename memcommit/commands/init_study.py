"""Initialize one Study as an isolated participant/authority Profile pair."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.commands.study_name_dialog import choose_study_profile_name
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import (
    ProfileError,
    STUDY_BASELINE_PROFILE_NAME,
    generate_study_profile_name,
    init_study_profile,
)


def _is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "New Profile name; omit to edit a timestamped default in a "
                "terminal, or generate it automatically outside a terminal"
            )
        ),
    ] = None,
    baseline_profile: Annotated[
        str,
        typer.Option(
            "--from-profile",
            help=("Editable Study baseline whose Task/grant topology will be copied"),
        ),
    ] = STUDY_BASELINE_PROFILE_NAME,
) -> None:
    """Clone one live Study baseline and restore its real grants."""

    try:
        if name is None and _is_interactive_terminal():
            name = choose_study_profile_name(generate_study_profile_name())
            if name is None:
                typer.echo("Cancelled — no Study Profile was created.")
                return
        result = init_study_profile(baseline_profile, name=name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Initialized Study run '{display_escape_text(result.profile.name)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo("Baseline Profile: " + display_escape_text(result.baseline_profile_name))
    typer.echo("Participant Profile: " + display_escape_text(result.profile.name))
    typer.echo(
        "Granted-memory Profile: " + display_escape_text(result.authority_profile.name)
    )
    current = (
        display_escape_text(result.inspection.current_context)
        if result.inspection.current_context
        else "(none)"
    )
    typer.echo(
        f"Contexts {len(result.inspection.context_names)} · "
        f"Memories {result.inspection.ordinary_memory_count} · current={current}"
    )
    typer.echo(
        f"Granted Contexts {result.inspection.granted_context_count} · "
        f"Granted Memories {result.inspection.granted_memory_count}"
    )
    typer.echo(
        "Task-owned and granted-memory data were copied into isolated run "
        "Profiles and connected with real authority grants."
    )
    typer.echo(
        "Operational history starts empty; checkpoints, sessions, caches, locks, "
        "and run logs were not imported."
    )
    typer.echo(
        "Active Profile unchanged: " + display_escape_text(result.active_profile_name)
    )
    typer.echo("Use it with: mem profile " + display_escape_text(result.profile.name))
