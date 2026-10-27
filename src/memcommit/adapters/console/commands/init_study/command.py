"""Initialize independent Profiles from the prepared Study project folders."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import current_command_attempt_uid
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.providers.policy import (
    STUDY_PROVIDER_POLICY_DIGEST,
    STUDY_PROVIDER_POLICY_VERSION,
)
from memcommit.adapters.console.commands.init_study.name_dialog import (
    choose_study_profile_name,
)
from memcommit.adapters.console.commands.init_study.receipt import (
    render_study_init_receipt,
)
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
    study_run_identity,
)
from memcommit.application.operations.init_study.application import (
    generate_study_profile_name,
    initialize_study,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.command_ledger.study_actions import (
    StudyActionError,
    record_study_action_for_profile,
)


def _is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def cmd(
    ctx: typer.Context,
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "New Profile name; omit to edit a local-date study-YYMMDD-N default in a "
                "terminal, or generate it automatically outside a terminal"
            )
        ),
    ] = None,
) -> None:
    """Initialize a Study from its prepared project folders."""

    try:
        previous_profile = load_profile_registry().active
        if name is None and _is_interactive_terminal():
            name = choose_study_profile_name(generate_study_profile_name())
            if name is None:
                typer.echo("Cancelled — no Study Profile was created.")
                return
        result = initialize_study(
            name=name,
            provider_policy_version=STUDY_PROVIDER_POLICY_VERSION,
            provider_policy_digest=STUDY_PROVIDER_POLICY_DIGEST,
        )
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
            assert participant_identity is not None
            record_study_action_for_profile(
                previous_profile,
                attempt_uid=attempt_uid,
                event_kind="PROFILE_LEFT",
                other_profile_uid=result.profile.uid,
                other_profile_name=result.profile.name,
            )
            for profile in result.profiles:
                record_study_action_for_profile(
                    profile,
                    attempt_uid=attempt_uid,
                    event_kind="STUDY_CREATED",
                    role=participant_identity.role,
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
                "Error: Study projects were created, but their initial Study "
                "records could not be written: " + display_escape_text(str(error)),
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    render_study_init_receipt(result)
