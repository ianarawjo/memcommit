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
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisApplicationError,
    AtomizeAnalysisOpenRequest,
)
from memcommit.application.operations.atomize.analysis_runtime import (
    execute_atomize_analysis_open,
)
from memcommit.application.operations.atomize.domain import (
    AtomizeFrameOrigin,
    AtomizeImpactError,
    atomize_analysis_matches_context,
)
from memcommit.application.operations.atomize.workbench import (
    AtomizeWorkbenchError,
    atomize_workbench_declared_frames,
    atomize_workbench_response_digest,
)
from memcommit.application.operations.review.model import (
    ReviewError,
    atomize_review_declared_frames,
    atomize_review_matches_analysis,
    review_response_digest,
)
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text


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
            typer.echo("Atomize workbench saved. No Memory changes applied.")
    typer.secho(
        f"Resumed saved analysis [{analysis.uid[:8]}]; the provider was not called.",
        fg=typer.colors.CYAN,
    )


def run_atomize_impact(
    *,
    store: MemoryStore,
    context_name: str,
    show_all: bool,
    with_review: bool,
    refresh: bool,
    memory_selector: str | None,
) -> None:
    """Create once or resume the provisional atomization workbench."""

    if refresh and with_review:
        typer.secho(
            "Impact error: use either --refresh for an unframed reanalysis "
            "or --with-review for a reviewed reanalysis, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
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
        declared_frames: dict[str, str] = {}
        declared_frame_origins: dict[str, AtomizeFrameOrigin] = {}
        source_review_uid = None
        source_review_digest = None
        source_workbench = None
        if with_review:
            prior_analysis = store.load_atomize_analysis(ctx.uid)
            if prior_analysis is None:
                raise ReviewError("No saved atomize analysis exists for this Context.")
            if not atomize_analysis_matches_context(prior_analysis, ctx):
                raise ReviewError(
                    "The saved atomize analysis is stale for this Context. "
                    "Reviewed responses cannot be applied to changed source "
                    "Memories; run an explicit unframed --refresh first."
                )
            source_workbench = store.load_atomize_workbench(prior_analysis)
            if source_workbench is not None and source_workbench.answered_count:
                (
                    declared_frames,
                    declared_frame_origins,
                ) = atomize_workbench_declared_frames(
                    source_workbench,
                    prior_analysis,
                )
                if not declared_frames:
                    raise ReviewError(
                        "The workbench has responses, but none can become a "
                        "single-Memory atomization frame. Pairwise conflict "
                        "responses remain staged for reconcile."
                    )
                source_review_uid = source_workbench.uid
                source_review_digest = atomize_workbench_response_digest(
                    source_workbench
                )
            else:
                # Compatibility path for the earlier global atomize review.
                review = store.load_review_session()
                if review is None or not atomize_review_matches_analysis(
                    review,
                    ctx,
                    prior_analysis,
                ):
                    raise ReviewError(
                        "No current atomize workbench response matches this "
                        "Context and analysis. Review an issue first."
                    )
                declared_frames = atomize_review_declared_frames(review)
                if not declared_frames:
                    raise ReviewError(
                        "The atomize review has no saved context or comments."
                    )
                source_review_uid = review.uid
                source_review_digest = review_response_digest(review)
                if review.source_analysis_uid is None:
                    raise ReviewError(
                        "The atomize review has no source analysis identity."
                    )
                item_by_memory_uid = {
                    item.source_uids[0]: item for item in review.items
                }
                declared_frame_origins = {
                    memory_uid: AtomizeFrameOrigin(
                        review_item_uid=item_by_memory_uid[memory_uid].uid,
                        source_analysis_uid=review.source_analysis_uid,
                        uncertainty_reason=(item_by_memory_uid[memory_uid].reason),
                    )
                    for memory_uid in declared_frames
                }

        def validate_review_before_save() -> None:
            if not with_review:
                return
            if source_workbench is not None and source_workbench.answered_count:
                latest_workbench = store.load_atomize_workbench(prior_analysis)
                if (
                    latest_workbench is None
                    or latest_workbench.uid != source_review_uid
                    or atomize_workbench_response_digest(latest_workbench)
                    != source_review_digest
                ):
                    raise AtomizeImpactError(
                        "The atomize workbench changed while reanalysis was "
                        "running; no preview was saved."
                    )
                return
            latest_review = store.load_review_session()
            if (
                latest_review is None
                or latest_review.uid != source_review_uid
                or review_response_digest(latest_review) != source_review_digest
            ):
                raise AtomizeImpactError(
                    "The atomize review changed while reanalysis was "
                    "running; no preview was saved."
                )

        with progressing_provider_factory(
            "IMPACT ATOMIZE",
            "analyzing memory structure",
            connect_codex_chatgpt_provider,
        ) as provider_factory:
            opened = execute_atomize_analysis_open(
                AtomizeAnalysisOpenRequest(
                    context=ctx,
                    refresh=refresh or with_review,
                    declared_frames=declared_frames,
                    declared_frame_origins=declared_frame_origins,
                    source_review_uid=source_review_uid,
                    source_review_digest=source_review_digest,
                    memory_selector=memory_selector,
                    allow_prepared=(
                        not refresh and not with_review and memory_selector is None
                    ),
                ),
                store=store,
                provider_factory=provider_factory,
                validate_before_save=validate_review_before_save,
            )
        analysis = opened.analysis
        workbench = opened.workbench
    except (
        AtomizeAnalysisApplicationError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        OSError,
        QueryProviderError,
        ReviewError,
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
            typer.echo("Atomize workbench saved. No Memory changes applied.")
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
    if analysis.declared_frames and opened.created_analysis:
        typer.secho(
            f"Incorporated {len(analysis.declared_frames)} reviewed declared "
            f"{'frame' if len(analysis.declared_frames) == 1 else 'frames'}.",
            fg=typer.colors.CYAN,
        )


__all__ = ["open_saved_atomize_impact", "run_atomize_impact"]
