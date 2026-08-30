"""Atomize-owned console adapter for ``mem impact atomize``."""

from __future__ import annotations

import sys

import typer

from memcommit.adapters.console.commands.atomize.sessions import (
    load_saved_atomize_analysis,
    revalidate_saved_atomize_analysis,
)
from memcommit.adapters.console.commands.atomize.workbench.screen import (
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.adapters.console.coordination.review import ReviewCancelled
from memcommit.adapters.console.terminal.components.progress import (
    progressing_provider_factory,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisApplicationError,
    AtomizeAnalysisOpenRequest,
)
from memcommit.application.operations.atomize.analysis_runtime import (
    execute_atomize_analysis_open,
)
from memcommit.application.operations.atomize.domain import AtomizeImpactError
from memcommit.application.operations.atomize.workbench import AtomizeWorkbenchError
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)


def open_saved_atomize_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
    show_all: bool = False,
) -> None:
    """Open one exact Atomize analysis without a create or refresh fallback."""

    if session_uid is None:
        raise ValueError("Saved Atomize Impact requires an exact session UID.")
    analysis = load_saved_atomize_analysis(store, session_uid)
    revalidate_saved_atomize_analysis(store, analysis)
    workbench = store.load_atomize_workbench(analysis)
    if workbench is None:
        raise ValueError(
            "The saved Atomize workbench is unavailable. Run "
            "'mem impact atomize CONTEXT' to reopen or explicitly refresh "
            "that Context."
        )
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(
            render_atomize_workbench_snapshot(
                workbench,
                analysis,
                show_all=show_all,
            )
        )
    else:
        try:
            run_atomize_workbench_shell(
                workbench,
                analysis,
                save=store.save_atomize_workbench,
            )
        except ReviewCancelled:
            typer.echo("Atomize workbench closed. No Memory changes applied.")
    typer.secho(
        f"Resumed saved analysis [{analysis.uid[:8]}]; the provider was not called.",
        fg=typer.colors.CYAN,
    )


def run_atomize_impact(
    *,
    store: MemoryStore,
    context_name: str,
    show_all: bool,
    refresh: bool,
    memory_selector: str | None,
) -> None:
    """Create once or resume one provisional atomization workbench."""

    try:
        ctx = store.load_direct(context_name)
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        with progressing_provider_factory(
            "IMPACT ATOMIZE",
            "analyzing memory structure",
            connect_codex_chatgpt_provider,
        ) as provider_factory:
            opened = execute_atomize_analysis_open(
                AtomizeAnalysisOpenRequest(
                    context=ctx,
                    refresh=refresh,
                    memory_selector=memory_selector,
                    allow_prepared=not refresh and memory_selector is None,
                ),
                store=store,
                provider_factory=provider_factory,
            )
        analysis = opened.analysis
        workbench = opened.workbench
    except (
        AtomizeAnalysisApplicationError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        OSError,
        QueryProviderError,
        ValueError,
    ) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(
            render_atomize_workbench_snapshot(
                workbench,
                analysis,
                show_all=show_all,
            )
        )
    else:
        try:
            run_atomize_workbench_shell(
                workbench,
                analysis,
                save=store.save_atomize_workbench,
            )
        except ReviewCancelled:
            typer.echo("Atomize workbench closed. No Memory changes applied.")
    if opened.materialized_prepared:
        typer.secho(
            f"Exact prewarm materialized [{analysis.uid[:8]}] on first use; "
            "the provider was not called.",
            fg=typer.colors.CYAN,
        )
    elif opened.created_analysis:
        typer.secho(
            f"Analysis saved [{analysis.uid[:8]}] for mem trace/rationale.",
            fg=typer.colors.CYAN,
        )
    else:
        typer.secho(
            f"Resumed saved analysis [{analysis.uid[:8]}]; "
            "the provider was not called.",
            fg=typer.colors.CYAN,
        )
    typer.echo(f"REOPEN · mem impact atomize --session {analysis.uid}")
    typer.echo("BROWSE ATOMIZE · mem impact atomize --sessions")
    typer.echo("BROWSE ALL IMPACT · mem impact --sessions")


__all__ = ["open_saved_atomize_impact", "run_atomize_impact"]
