"""Import a clean MemoryStore baseline as a new isolated Profile."""

from pathlib import Path
from typing import Annotated

import typer

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError, import_baseline_profile


def cmd(
    name: Annotated[str, typer.Argument(help="New baseline Profile name")],
    source: Annotated[
        Path,
        typer.Option("--from", help="Source .mem store or package directory"),
    ],
) -> None:
    """Import content identity while starting history and sessions empty."""

    try:
        profile, inspection = import_baseline_profile(name, source)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Imported clean baseline Profile '{display_escape_text(profile.name)}'.",
        fg=typer.colors.GREEN,
    )
    current = (
        display_escape_text(inspection.current_context)
        if inspection.current_context
        else "(none)"
    )
    typer.echo(
        f"Contexts {len(inspection.context_names)} · "
        f"Memories {inspection.ordinary_memory_count} · current={current}"
    )
    source_record = profile.source or {}
    typer.echo("Baseline SHA-256: " + str(source_record.get("baseline_sha256", "")))
    typer.echo(
        "Checkpoint history, sessions, caches, locks, and run logs were not imported."
    )
    typer.echo("The source store and active Profile were not changed.")
