"""Console handlers for ordinary Profile lifecycle and selection accounting."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.profile._support import _fail
from memcommit.adapters.console.commands.profile.presentation import (
    _inventory_label,
    _print_profile_creation,
    _print_profile_removal,
    _print_profile_rename,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
)
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.application.operations.profile.model.lifecycle import (
    create_profile,
    import_profile,
    remove_profile,
    rename_profile,
    use_profile,
)
from memcommit.persistence.command_ledger.attempts import current_command_attempt_uid
from memcommit.persistence.command_ledger.study_actions import (
    StudyActionError,
    record_study_action,
    record_study_action_for_profile,
)


def _use_profile(name: str) -> None:
    try:
        previous_profile = load_profile_registry().active
        registry, inspection, changed = use_profile(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    if not changed:
        typer.echo(
            "Already using profile '" + display_escape_text(registry.active.name) + "'."
        )
        return
    attempt_uid = current_command_attempt_uid()
    if attempt_uid is not None:
        try:
            record_study_action(
                "PROFILE_LEFT",
                other_profile_uid=registry.active.uid,
                other_profile_name=registry.active.name,
            )
            record_study_action_for_profile(
                registry.active,
                attempt_uid=attempt_uid,
                event_kind="PROFILE_ENTERED",
                other_profile_uid=previous_profile.uid,
                other_profile_name=previous_profile.name,
            )
        except (OSError, ProfileConfigError, StudyActionError, ValueError) as error:
            typer.secho(
                "Error: Profile selection changed, but its Study action ledger "
                "could not be written: " + display_escape_text(str(error)),
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
    typer.secho(
        f"Selected profile '{display_escape_text(registry.active.name)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo("The next mem command will see " + _inventory_label(inspection) + ".")
    current_label = (
        display_escape_text(inspection.current_context)
        if inspection.current_context
        else "(none)"
    )
    typer.echo(f"Current Context: {current_label}")
    if inspection.query_source_count:
        typer.echo(
            "Query-only: "
            f"{', '.join(display_escape_text(name) for name in inspection.query_source_names)} "
            "(visible by name; hidden from 'mem switch')."
        )


def create_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Unique name for the new empty managed Profile"),
    ],
) -> None:
    """Create one empty managed Profile without selecting it."""

    try:
        result = create_profile(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    _print_profile_creation(result)


def remove_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Managed Profile whose complete store will be deleted"),
    ],
    force: Annotated[
        bool,
        typer.Option("-f", "--force", help="Skip the confirmation prompt"),
    ] = False,
) -> None:
    """Permanently delete one Profile store and all of its checkpoints."""

    if not force:
        typer.echo(
            "WARNING: This permanently deletes only Profile '"
            + display_escape_text(name)
            + "', its complete store, every Memory, session, and checkpoint, "
            "plus connected Grants. This cannot be undone or recovered by mem."
        )
        if not typer.confirm("Continue?", default=False):
            typer.echo("Profile removal cancelled.")
            return
    try:
        with CommandProgress(
            "profile remove",
            "deleting store and checkpoints",
            total=1,
        ):
            result = remove_profile(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    _print_profile_removal(result)


def rename_cmd(
    profile_or_new: Annotated[
        str,
        typer.Argument(
            metavar="NAME",
            help=(
                "New name for the current Profile, or existing Profile when "
                "NEW is also supplied"
            ),
        ),
    ],
    new_name: Annotated[
        Optional[str],
        typer.Argument(
            metavar="NEW",
            help="New name for the explicitly named Profile",
        ),
    ] = None,
) -> None:
    """Rename one managed Profile without moving or rewriting its store."""

    old_name = profile_or_new if new_name is not None else None
    destination = new_name if new_name is not None else profile_or_new
    try:
        result = rename_profile(destination, old_name=old_name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    _print_profile_rename(result)


def import_cmd(
    name: Annotated[str, typer.Argument(help="New managed profile name")],
    source: Annotated[
        Path,
        typer.Option("--from", help="Complete .mem store or package directory"),
    ],
) -> None:
    """Copy one complete store into a new editable managed profile."""

    try:
        profile, inspection = import_profile(name, source)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho(
        f"Imported profile '{display_escape_text(profile.name)}'.",
        fg=typer.colors.GREEN,
    )
    current_label = (
        display_escape_text(inspection.current_context)
        if inspection.current_context
        else "(none)"
    )
    typer.echo(f"{_inventory_label(inspection)} · current={current_label}")
    typer.echo("The source store was not modified.")
