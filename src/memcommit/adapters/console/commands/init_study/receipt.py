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
    """Print the prepared project folder and its initial Study state."""

    typer.secho(
        f"Initialized Study run '{display_escape_text(result.study_name)}'.",
        fg=typer.colors.GREEN,
    )
    echo_text(
        "Provider config: {version} · locked · sha256 {digest}",
        version=STUDY_PROVIDER_POLICY_VERSION,
        digest=STUDY_PROVIDER_POLICY_DIGEST,
    )
    echo_text(
        "Contexts {contexts} · Memories {memories} · current={current}",
        contexts=sum(len(inspection.context_names) for inspection in result.inspections),
        memories=sum(inspection.ordinary_memory_count for inspection in result.inspections),
        current=result.inspection.current_context or "(none)",
    )
    for profile, inspection in zip(result.profiles, result.inspections, strict=True):
        echo_text("Profile: {name} · Contexts {count}", name=profile.name, count=len(inspection.context_names))
        echo_text("  Project folder: {path}", path=profile.root_dir)
        echo_text("  Select: mem profile use {name}", name=profile.name)
    echo_text("Study records: {path}", path=result.records_root)
    typer.echo("Markdown files and .mem are ready. Edit files, then run mem sync.")
    typer.echo("Open any Project folder in your editor. All projects start in Sync.")
    typer.echo(
        "Initial Sync checkpoints are ready; participant Undo/Redo starts empty. "
        "Earlier operation history, sessions, caches and locks were not imported."
    )
    echo_text("Active Profile: {name}", name=result.active_profile_name)
