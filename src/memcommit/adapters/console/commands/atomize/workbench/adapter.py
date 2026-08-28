"""Compose Atomize application state into its terminal workbench."""

from __future__ import annotations

import sys

import typer

from memcommit.application.operations.atomize.domain import AtomizeAnalysisSession
from memcommit.application.operations.atomize.workbench import AtomizeWorkbenchSession
from memcommit.adapters.console.commands.atomize.workbench.screen import (
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.adapters.console.coordination.review import ReviewCancelled
from memcommit.adapters.console.terminal.components.resolution import ResolutionDestination
from memcommit.application.capabilities.resolution.workbench import ResolutionWorkbenchAction
from memcommit.persistence.store import MemoryStore


def present_atomize_workbench(
    *,
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
    show_all: bool,
    workflow_actions: bool = True,
    application_complete: bool = False,
) -> ResolutionWorkbenchAction | None:
    """Present one saved workbench without owning Atomize application policy."""

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(
            render_atomize_workbench_snapshot(
                workbench,
                analysis,
                show_all=show_all,
            )
        )
        return None

    planned_output = workbench.output_context_name or analysis.context_name

    def validate_destination(name: str) -> None:
        if name == analysis.context_name:
            raise ValueError(
                "A distinct Atomize Output cannot be changed to the Input "
                "Context from Save Location."
            )
        store.assert_context_creatable(name)

    try:
        result = run_atomize_workbench_shell(
            workbench,
            analysis,
            save=store.save_atomize_workbench,
            workflow_actions=workflow_actions,
            application_complete=application_complete,
            destination=(
                ResolutionDestination(
                    value=planned_output,
                    state="CREATE ON APPLY",
                    detail=(
                        "Enter to change this exact new Context name before "
                        "Review and Apply."
                    ),
                    validate=validate_destination,
                    context_names=tuple(store.list_context_names()),
                    current_context=store.current_context_name(),
                )
                if workflow_actions and planned_output != analysis.context_name
                else None
            ),
        )
        return result if isinstance(result, ResolutionWorkbenchAction) else None
    except ReviewCancelled:
        typer.echo("Atomize workbench saved. No Memory changes applied.")
        return None
