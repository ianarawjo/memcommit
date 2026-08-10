"""Initialize one Study as an isolated participant/authority Profile pair."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.command_attempts import current_command_attempt_uid
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.commands.study_name_dialog import choose_study_profile_name
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    study_run_identity,
)
from memcommit.profiles import (
    ProfileError,
    STUDY_BASELINE_PROFILE_NAME,
    generate_study_profile_name,
    init_study_profile,
)
from memcommit.study_action_log import (
    StudyActionError,
    record_study_action,
    record_study_action_for_profile,
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
        previous_profile = load_profile_registry().active
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

    attempt_uid = current_command_attempt_uid()
    if attempt_uid is not None:
        try:
            participant_identity = study_run_identity(result.profile)
            authority_identity = study_run_identity(result.authority_profile)
            assert participant_identity is not None
            assert authority_identity is not None
            record_study_action(
                "PROFILE_LEFT",
                other_profile_uid=result.profile.uid,
                other_profile_name=result.profile.name,
            )
            for profile, identity, paired_profile in (
                (
                    result.profile,
                    participant_identity,
                    result.authority_profile,
                ),
                (
                    result.authority_profile,
                    authority_identity,
                    result.profile,
                ),
            ):
                record_study_action_for_profile(
                    profile,
                    attempt_uid=attempt_uid,
                    event_kind="STUDY_CREATED",
                    role=identity.role,
                    paired_profile_uid=paired_profile.uid,
                    baseline_profile_uid=identity.baseline_profile_uid,
                    baseline_profile_name=identity.baseline_profile_name,
                )
            record_study_action_for_profile(
                result.profile,
                attempt_uid=attempt_uid,
                event_kind="PROFILE_ENTERED",
                other_profile_uid=previous_profile.uid,
                other_profile_name=previous_profile.name,
            )
        except (OSError, ProfileConfigError, StudyActionError, ValueError) as error:
            typer.secho(
                "Error: Study Profiles were created, but their initial action "
                "ledger could not be written: " + display_escape_text(str(error)),
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
    typer.echo("Active Profile: " + display_escape_text(result.active_profile_name))
