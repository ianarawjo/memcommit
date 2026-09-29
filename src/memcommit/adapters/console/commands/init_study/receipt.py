"""Console receipt for a completed Study initialization."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.output import echo_text
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.init_study.model import StudyInitializationResult
from memcommit.providers.policy import (
    STUDY_PROVIDER_POLICY_DIGEST,
    STUDY_PROVIDER_POLICY_VERSION,
)


def render_study_init_receipt(result: StudyInitializationResult) -> None:
    """Print the completed Profile pair and its initial Study state."""

    typer.secho(
        f"Initialized Study run '{display_escape_text(result.profile.name)}'.",
        fg=typer.colors.GREEN,
    )
    echo_text("Scenario: {name}", name=result.scenario_id)
    echo_text("Participant Profile: {name}", name=result.profile.name)
    echo_text("Granted-memory Profile: {name}", name=result.authority_profile.name)
    echo_text(
        "Provider config: {version} · locked · sha256 {digest}",
        version=STUDY_PROVIDER_POLICY_VERSION,
        digest=STUDY_PROVIDER_POLICY_DIGEST,
    )
    echo_text(
        "Contexts {contexts} · Memories {memories} · current={current}",
        contexts=len(result.inspection.context_names),
        memories=result.inspection.ordinary_memory_count,
        current=result.inspection.current_context or "(none)",
    )
    echo_text(
        "Granted Contexts {contexts} · Granted Memories {memories}",
        contexts=result.inspection.granted_context_count,
        memories=result.inspection.granted_memory_count,
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
    echo_text("Active Profile: {name}", name=result.active_profile_name)
