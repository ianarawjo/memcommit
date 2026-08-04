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
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.granted_context import (
    ContextAccess,
    GrantedReadStore,
    attached_grants,
    resolve_context_access,
)
from memcommit.commands.review_shell import ReviewCancelled
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.commands.update_render import (
    render_plan,
    run_update_workbench,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.review import (
    ReviewError,
    atomize_review_declared_frames,
    atomize_review_matches_analysis,
    review_response_digest,
)
from memcommit.store import MemoryStore
from memcommit.update import (
    GrantedUpdateTarget,
    UpdateError,
    granted_target_digest,
    plan_update,
    session_matches,
)
from memcommit.update_endpoints import resolve_update_endpoints


class ImpactOperation(str, Enum):
    """Unary operations supported by the impact preview command."""

    atomize = "atomize"


def _usage_error(message: str) -> None:
    typer.secho(f"Impact error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(2)


def _granted_update_target(access: ContextAccess) -> GrantedUpdateTarget:
    """Freeze the control-plane identity behind one public target view."""

    view = access.view
    if view is None:
        raise UpdateError("Expected a granted update target.")
    grant = view.grant
    return GrantedUpdateTarget(
        public_name=access.display_name,
        grantee_profile_uid=view.grantee.uid,
        authority_profile_uid=view.authority.uid,
        attachment_context_uid=grant.attachment_context_uid,
        attachment_context_name=grant.attachment_context_name,
        grant_uid=grant.uid,
        grant_revision=grant.revision,
        grant_digest=granted_target_digest(grant.to_dict()),
        resource_uid=grant.resource_uid,
        resource_name=grant.resource_name,
        authority_context_name=view.authority_context_name,
        permissions=grant.permissions,
    )


def _directional_impact(
    *,
    store: MemoryStore,
    current_name: str | None,
    source_name: str | None,
    target_name: str | None,
) -> None:
    """Preview one explicit or current-filled directional endpoint pair."""
    try:
        endpoints = resolve_update_endpoints(
            source_locator=source_name,
            target_locator=target_name,
            current=current_name,
        )
        source = store.load(endpoints.source_name)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        if store.context_exists(endpoints.target_name):
            target = store.load(endpoints.target_name)
            session = plan_update(
                source,
                target,
                connect_codex_chatgpt_provider,
                status="impact",
            )
            store.save_impact_plan(session)
        else:
            if target_name is None:
                raise FileNotFoundError(
                    f"Context '{endpoints.target_name}' not found."
                )
            _registry, grants = attached_grants(endpoints.source_name)
            candidates = [
                grant
                for grant in grants
                if endpoints.target_name == grant.public_name
                or endpoints.target_name.startswith(grant.public_name + "/")
            ]
            if not candidates:
                raise FileNotFoundError(
                    f"Context '{endpoints.target_name}' not found."
                )
            effective = max(
                candidates,
                key=lambda grant: len(grant.public_name.split("/")),
            )
            if "READ" not in effective.permissions:
                raise ProfileError(
                    f"Grant {effective.uid[:8]} does not allow read access to "
                    f"{endpoints.target_name!r}."
                )
            # Authenticate before opening any authority-owned target content.
            provider = connect_codex_chatgpt_provider()
            with authority_grant_snapshot_lock() as registry:
                access = resolve_context_access(
                    store,
                    target_name,
                    current_name=endpoints.source_name,
                    required_permission="READ",
                    registry=registry,
                )
                if not access.is_granted:
                    raise UpdateError("Expected a granted update target.")
                target = GrantedReadStore(access, registry=registry).load(
                    access.display_name
                )
                granted_target = _granted_update_target(access)

            session = plan_update(
                source,
                target,
                lambda: provider,
                status="impact",
                granted_target=granted_target,
            )

            # A provider turn is not an authorization lease. Rebuild the same
            # projection under the registry lock and publish the plan only if
            # the source, grant, and readable target remain exact.
            with authority_grant_snapshot_lock() as registry:
                current_access = resolve_context_access(
                    store,
                    granted_target.public_name,
                    current_name=granted_target.attachment_context_name,
                    required_permission="READ",
                    registry=registry,
                )
                if not current_access.is_granted:
                    raise UpdateError(
                        "The granted target changed while planning; no preview "
                        "was saved."
                    )
                current_granted_target = _granted_update_target(current_access)
                current_target = GrantedReadStore(
                    current_access,
                    registry=registry,
                ).load(current_access.display_name)
                current_source = store.load(endpoints.source_name)
                if not session_matches(
                    session,
                    current_source,
                    current_target,
                    granted_target=current_granted_target,
                ):
                    raise UpdateError(
                        "The update source or granted target changed while "
                        "planning; no preview was saved."
                    )
                store.save_impact_plan(session)
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        UpdateError,
        ValueError,
    ) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if sys.stdin.isatty() and sys.stdout.isatty():
        run_update_workbench(session)
    else:
        render_plan(session, staged=False)


def _atomize_impact(
    *,
    store: MemoryStore,
    context_name: str,
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
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=("Source Context A; if --to is omitted, current supplies B"),
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=("Target Context B; if --from is omitted, current supplies A"),
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
        if source_name is not None or target_name is not None:
            _usage_error(
                "'atomize' cannot be combined with '--from' or '--to'. "
                "Use either 'mem impact atomize' or "
                "a directional 'mem impact --from SOURCE' / "
                "'--to TARGET' form."
            )
        try:
            store = MemoryStore(create=False)
            context_snapshot = ContextOperandSnapshot.capture(store)
            canonical_context_name = context_snapshot.resolve_or_current(context_name)
            if not canonical_context_name:
                raise AtomizeImpactError(
                    "No current context. Pass --context or run 'mem init <name>' first."
                )
        except (OSError, RuntimeError, ValueError) as error:
            typer.secho(
                f"Impact error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        _atomize_impact(
            store=store,
            context_name=canonical_context_name,
            show_all=show_all,
            with_review=with_review,
            refresh=refresh,
        )
        return

    if source_name is None and target_name is None:
        _usage_error(
            "choose an endpoint with '--from SOURCE' or '--to TARGET', or "
            "preview atomization with 'mem impact atomize'."
        )
    if context_name is not None or show_all or with_review or refresh:
        _usage_error(
            "'--context', '--all', '--with-review', and '--refresh' are only "
            "valid with "
            "'mem impact atomize'."
        )
    try:
        store = MemoryStore()
        context_snapshot = ContextOperandSnapshot.capture(store)
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    _directional_impact(
        store=store,
        current_name=context_snapshot.current_name,
        source_name=source_name,
        target_name=target_name,
    )
