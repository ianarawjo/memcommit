"""Console handlers for the Profiles belonging to a Study."""

from __future__ import annotations

from typing import Annotated

import typer

from memcommit.adapters.console.commands.profile._support import _fail
from memcommit.adapters.console.commands.profile.presentation import (
    _print_study_removal,
    _print_study_rename,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.application.operations.profile.model.study import (
    archive_legacy_study,
    remove_study,
    rename_study,
)


def remove_study_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Legacy or current Study name"),
    ],
    force: Annotated[
        bool,
        typer.Option("-f", "--force", help="Skip the confirmation prompt"),
    ] = False,
) -> None:
    """Permanently delete every Profile store and checkpoint in one Study."""

    if not force:
        typer.echo(
            "WARNING: This permanently deletes every Profile in Study '"
            + display_escape_text(name)
            + "', including every store, Memory, session, checkpoint, and "
            "connected Grant. This cannot be undone or recovered by mem."
        )
        if not typer.confirm("Continue?", default=False):
            typer.echo("Study removal cancelled.")
            return
    try:
        with CommandProgress(
            "profile remove-study",
            "deleting stores and checkpoints",
            total=1,
        ):
            result = remove_study(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    _print_study_removal(result)


def rename_study_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Current or legacy Study name"),
    ],
    new_name: Annotated[
        str,
        typer.Argument(help="New Study display name"),
    ],
) -> None:
    """Rename one complete Study without moving any member store."""

    try:
        result = rename_study(name, new_name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    _print_study_rename(result)


def archive_study_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Complete legacy split Study name"),
    ],
) -> None:
    """Detach a legacy split Study while preserving all of its store data."""

    try:
        result = archive_legacy_study(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho(
        "Archived legacy Study '" + display_escape_text(result.name) + "'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Profiles removed from selector: {len(result.profiles)}")
    typer.echo(f"Internal grants recorded in archive: {len(result.grants)}")
    typer.echo("Archive manifest: " + display_escape_text(str(result.manifest_path)))
    typer.echo(
        "Active Profile unchanged: " + display_escape_text(result.active_profile_name)
    )
    typer.echo("No Memory data was moved or deleted.")
    typer.echo("To create a merged replacement from an available Study baseline:")
    typer.echo("  mem init-study " + display_escape_text(result.name))
