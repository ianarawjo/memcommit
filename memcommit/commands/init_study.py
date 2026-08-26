"""Initialize one Study as an isolated participant/authority Profile pair."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.infrastructure.command_ledger.attempts import current_command_attempt_uid
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.infrastructure.providers.policy import (
    STUDY_PROVIDER_POLICY_DIGEST,
    STUDY_PROVIDER_POLICY_VERSION,
)
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
    init_coffee_study_profile,
    init_study_profile,
)
from memcommit.study_scenarios import COFFEE_V1_SCENARIO_ID
from memcommit.infrastructure.command_ledger.study_actions import (
    StudyActionError,
    record_study_action,
    record_study_action_for_profile,
)


def _is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _show_prewarm_progress(event: str) -> None:
    fields = event.split()
    if not fields:
        return
    if fields[0] == "CHECK":
        typer.echo("Checking shared Study cache compatibility...")
    elif fields[0] == "READY" and len(fields) == 2 and fields[1] != "0":
        typer.echo("Shared Study caches verified.")
    elif fields[0] == "REFRESH_START" and len(fields) == 2:
        typer.echo(
            "Refreshing incompatible shared Study caches "
            f"with {fields[1]} workers..."
        )
    elif fields[0] == "REFRESH_PROGRESS" and len(fields) == 3:
        completed = int(fields[1])
        total = int(fields[2])
        percentage = min(100, (completed * 100) // total) if total else 100
        typer.echo(f"Shared Study cache refresh {percentage}%.")
    elif fields[0] == "REFRESH_COMPLETE" and len(fields) == 2:
        typer.echo("Shared Study cache refresh complete.")


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
    scenario: Annotated[
        Optional[str],
        typer.Option(
            "--scenario",
            show_default=False,
            help=(
                "Versioned Study scenario: coffee-v1 (default) or legacy-v1 "
                "for the preserved debugging fixture"
            ),
        ),
    ] = None,
    baseline_profile: Annotated[
        Optional[str],
        typer.Option(
            "--from-profile",
            show_default=False,
            help=(
                "Editable legacy Study baseline to copy; supplying this option "
                "without --scenario implies legacy-v1"
            ),
        ),
    ] = None,
    prewarm_workers: Annotated[
        int,
        typer.Option(
            "--prewarm-workers",
            min=1,
            help=(
                "Maximum parallel workers used only when declared Study caches "
                "must be regenerated"
            ),
        ),
    ] = 96,
    prewarm_reasoning: Annotated[
        str,
        typer.Option(
            "--prewarm-reasoning",
            help=(
                "Codex reasoning effort used only to regenerate shared Study "
                "Compare caches"
            ),
        ),
    ] = "xhigh",
) -> None:
    """Initialize the Coffee Study, or explicitly reproduce the legacy fixture."""

    try:
        resolved_scenario = scenario or (
            "legacy-v1" if baseline_profile is not None else COFFEE_V1_SCENARIO_ID
        )
        if resolved_scenario not in {COFFEE_V1_SCENARIO_ID, "legacy-v1"}:
            raise ProfileError("Study scenario must be 'coffee-v1' or 'legacy-v1'.")
        if resolved_scenario == COFFEE_V1_SCENARIO_ID and baseline_profile is not None:
            raise ProfileError("--from-profile can be used only with legacy-v1.")
        previous_profile = load_profile_registry().active
        if name is None and _is_interactive_terminal():
            name = choose_study_profile_name(generate_study_profile_name())
            if name is None:
                typer.echo("Cancelled — no Study Profile was created.")
                return
        if resolved_scenario == COFFEE_V1_SCENARIO_ID:
            result = init_coffee_study_profile(
                name=name,
                provider_policy_version=STUDY_PROVIDER_POLICY_VERSION,
                provider_policy_digest=STUDY_PROVIDER_POLICY_DIGEST,
            )
        else:
            result = init_study_profile(
                baseline_profile or STUDY_BASELINE_PROFILE_NAME,
                name=name,
                provider_policy_version=STUDY_PROVIDER_POLICY_VERSION,
                provider_policy_digest=STUDY_PROVIDER_POLICY_DIGEST,
                prewarm_workers=prewarm_workers,
                prewarm_reasoning=prewarm_reasoning,
                prewarm_progress=_show_prewarm_progress,
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
    if result.scenario_id == "legacy-v1":
        typer.echo(
            "Baseline Profile: " + display_escape_text(result.baseline_profile_name)
        )
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
    if any(
        (
            result.declared_compare_prewarms,
            result.declared_atomize_prewarms,
            result.declared_summarize_prewarms,
            result.declared_update_prewarms,
            result.declared_sever_prewarms,
            result.declared_directional_meld_prewarms,
            result.declared_meld_resolution_prewarms,
        )
    ):
        # Setup diagnostics must not prime participants with operation names or
        # reveal which measured task has a prepared semantic path.
        typer.echo("Shared Study prewarm bundle attached.")
    if result.scenario_id == COFFEE_V1_SCENARIO_ID:
        typer.echo(
            "Operational history starts empty; no shared semantic prewarm was "
            "attached. Checkpoints, sessions, ad-hoc caches, locks, and run logs "
            "were not imported."
        )
    else:
        typer.echo(
            "Operational history starts empty; declared caches remain hidden until "
            "the first matching operation. Checkpoints, sessions, ad-hoc caches, "
            "locks, and run logs were not imported."
        )
    typer.echo("Active Profile: " + display_escape_text(result.active_profile_name))
