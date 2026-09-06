"""Initialize one Study as an isolated participant/authority Profile pair."""

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
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
    study_run_identity,
)
from memcommit.application.operations.init_study.application import (
    generate_study_profile_name,
    init_coffee_study_profile,
    init_legacy_study_profile,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.study_scenarios import COFFEE_SCENARIO_ID, LEGACY_SCENARIO_ID
from memcommit.persistence.command_ledger.study_actions import (
    StudyActionError,
    record_study_action,
    record_study_action_for_profile,
)
from memcommit.adapters.console.commands.init_study.study_shell import (
    schedule_study_shell,
    should_enter_study_shell,
)


def _is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def cmd(
    ctx: typer.Context,
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "New Profile name; omit to edit a timestamped default in a "
                "terminal, or generate it automatically outside a terminal"
            )
        ),
    ] = None,
    scenario: Annotated[
        Optional[str],
        typer.Option(
            "--scenario",
            show_default=False,
            help=(
                "Study scenario: coffee (default) or legacy "
                "for the preserved debugging fixture"
            ),
        ),
    ] = None,
) -> None:
    """Initialize the Coffee Study, or explicitly reproduce the legacy fixture."""

    try:
        resolved_scenario = scenario or COFFEE_SCENARIO_ID
        if resolved_scenario not in {COFFEE_SCENARIO_ID, LEGACY_SCENARIO_ID}:
            raise ProfileError("Study scenario must be 'coffee' or 'legacy'.")
        previous_profile = load_profile_registry().active
        if name is None and _is_interactive_terminal():
            name = choose_study_profile_name(generate_study_profile_name())
            if name is None:
                typer.echo("Cancelled — no Study Profile was created.")
                return
        if resolved_scenario == COFFEE_SCENARIO_ID:
            result = init_coffee_study_profile(
                name=name,
                provider_policy_version=STUDY_PROVIDER_POLICY_VERSION,
                provider_policy_digest=STUDY_PROVIDER_POLICY_DIGEST,
            )
        else:
            result = init_legacy_study_profile(
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
    typer.echo("Scenario: " + display_escape_text(result.scenario_id))
    typer.echo("Participant Profile: " + display_escape_text(result.profile.name))
    typer.echo(
        "Granted-memory Profile: " + display_escape_text(result.authority_profile.name)
    )
    typer.echo(
        "Provider config: "
        f"{STUDY_PROVIDER_POLICY_VERSION} · locked · "
        f"sha256 {STUDY_PROVIDER_POLICY_DIGEST}"
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
        "Operational history starts empty. "
        "Checkpoints, sessions, ad-hoc caches, locks, and run logs "
        "were not imported."
    )
    typer.echo("Active Profile: " + display_escape_text(result.active_profile_name))
    if should_enter_study_shell():
        typer.echo("Study shell: opens after this initialization attempt is recorded.")
        schedule_study_shell(ctx, result.active_profile_name)
