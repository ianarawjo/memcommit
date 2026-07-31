"""Preview directional updates or unary semantic Context operations."""
import sys
from enum import Enum
from typing import Annotated, Optional

import typer

from memcommit.atomize import (
    AtomizeFrameOrigin,
    AtomizeImpactError,
    atomize_analysis_matches_context,
)
from memcommit.atomize_workflow import open_or_create_atomize_workbench
from memcommit.atomize_workbench import (
    AtomizeWorkbenchError,
    atomize_workbench_declared_frames,
    atomize_workbench_response_digest,
)
from memcommit.commands.atomize_workbench_shell import (
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.commands.review_shell import ReviewCancelled
from memcommit.commands.update_render import (
    render_plan,
    run_update_workbench,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.review import (
    ReviewError,
    atomize_review_declared_frames,
    atomize_review_matches_analysis,
    review_response_digest,
)
from memcommit.store import MemoryStore
from memcommit.update import UpdateError, plan_update


class ImpactOperation(str, Enum):
    """Unary operations supported by the impact preview command."""

    atomize = "atomize"


def _usage_error(message: str) -> None:
    typer.secho(f"Impact error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(2)


def _directional_impact(target_name: str) -> None:
    """Preserve the existing current-A to target-B impact behavior."""
    store = MemoryStore()
    try:
        current_name = store.current_context_name()
        if not current_name:
            raise RuntimeError("No current Context.")
        resolved_target_name = resolve_context_locator(
            target_name,
            current=current_name,
        )
        source = store.load(current_name)
        target = store.load(resolved_target_name)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        typer.secho(f"Impact error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        session = plan_update(
            source,
            target,
            connect_codex_chatgpt_provider,
            status="impact",
        )
        store.save_impact_plan(session)
    except (OSError, QueryProviderError, UpdateError, ValueError) as error:
        typer.secho(f"Impact error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if sys.stdin.isatty() and sys.stdout.isatty():
        run_update_workbench(session)
    else:
        render_plan(session, staged=False)


def _atomize_impact(
    *,
    context_name: str | None,
    show_all: bool,
    with_review: bool,
    refresh: bool,
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
    store = MemoryStore(create=False)
    try:
        ctx = (
            store.load_current_direct()
            if context_name is None
            else store.load_direct(context_name)
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(f"Impact error: {error}", fg=typer.colors.RED, err=True)
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
                raise ReviewError(
                    "No saved atomize analysis exists for this Context."
                )
            if not atomize_analysis_matches_context(prior_analysis, ctx):
                raise ReviewError(
                    "The saved atomize analysis is stale for this Context. "
                    "Reviewed responses cannot be applied to changed source "
                    "Memories; run an explicit unframed --refresh first."
                )
            source_workbench = store.load_atomize_workbench(prior_analysis)
            if (
                source_workbench is not None
                and source_workbench.answered_count
            ):
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
                if (
                    review is None
                    or not atomize_review_matches_analysis(
                        review,
                        ctx,
                        prior_analysis,
                    )
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
                    item.source_uids[0]: item
                    for item in review.items
                }
                declared_frame_origins = {
                    memory_uid: AtomizeFrameOrigin(
                        review_item_uid=item_by_memory_uid[memory_uid].uid,
                        source_analysis_uid=review.source_analysis_uid,
                        uncertainty_reason=(
                            item_by_memory_uid[memory_uid].reason
                        ),
                    )
                    for memory_uid in declared_frames
                }
        def validate_review_before_save() -> None:
            if not with_review:
                return
            if source_workbench is not None and source_workbench.answered_count:
                latest_workbench = store.load_atomize_workbench(
                    prior_analysis
                )
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
                or review_response_digest(latest_review)
                != source_review_digest
            ):
                raise AtomizeImpactError(
                    "The atomize review changed while reanalysis was "
                    "running; no preview was saved."
                )

        opened = open_or_create_atomize_workbench(
            store=store,
            ctx=ctx,
            provider_factory=connect_codex_chatgpt_provider,
            refresh=refresh or with_review,
            declared_frames=declared_frames,
            declared_frame_origins=declared_frame_origins,
            source_review_uid=source_review_uid,
            source_review_digest=source_review_digest,
            validate_before_save=validate_review_before_save,
        )
        analysis = opened.analysis
        workbench = opened.workbench
    except (
        AtomizeImpactError,
        AtomizeWorkbenchError,
        OSError,
        QueryProviderError,
        ReviewError,
        ValueError,
    ) as error:
        typer.secho(f"Impact error: {error}", fg=typer.colors.RED, err=True)
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
    if opened.created_analysis:
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
    if analysis.declared_frames and opened.created_analysis:
        typer.secho(
            f"Incorporated {len(analysis.declared_frames)} reviewed declared "
            f"{'frame' if len(analysis.declared_frames) == 1 else 'frames'}.",
            fg=typer.colors.CYAN,
        )


def cmd(
    operation: Annotated[
        Optional[ImpactOperation],
        typer.Argument(
            help="Optional unary impact operation: atomize",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Target Context B to assess from the current Context A",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context for a unary impact operation (defaults to current)",
        ),
    ] = None,
    show_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Include unchanged ATOMIC Memories in atomize output",
        ),
    ] = False,
    with_review: Annotated[
        bool,
        typer.Option(
            "--with-review",
            help="Reanalyze using saved unary atomize workbench responses",
        ),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help=(
                "Explicitly replace the saved analysis with one new unframed "
                "semantic completion"
            ),
        ),
    ] = False,
) -> None:
    """Dispatch one of the two non-mutating impact preview forms."""
    if operation is ImpactOperation.atomize:
        if target_name is not None:
            _usage_error(
                "'atomize' cannot be combined with '--to'. "
                "Use either 'mem impact atomize' or "
                "'mem impact --to TARGET'."
            )
        _atomize_impact(
            context_name=context_name,
            show_all=show_all,
            with_review=with_review,
            refresh=refresh,
        )
        return

    if target_name is None:
        _usage_error(
            "choose a target with '--to TARGET' or preview atomization with "
            "'mem impact atomize'."
        )
    if context_name is not None or show_all or with_review or refresh:
        _usage_error(
            "'--context', '--all', '--with-review', and '--refresh' are only "
            "valid with "
            "'mem impact atomize'."
        )
    _directional_impact(target_name)
