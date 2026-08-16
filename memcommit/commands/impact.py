"""Preview new effects or inspect saved operation-owned Impact artifacts."""

from __future__ import annotations

import sys
from collections.abc import Callable
from enum import Enum
from typing import Annotated, Optional

import typer

from memcommit.atomize import (
    AtomizeFrameOrigin,
    AtomizeImpactError,
    atomize_analysis_matches_context,
)
from memcommit.atomize_analysis_application import (
    AtomizeAnalysisApplicationError,
    AtomizeAnalysisOpenRequest,
)
from memcommit.atomize_analysis_runtime import execute_atomize_analysis_open
from memcommit.atomize_workbench import (
    AtomizeWorkbenchError,
    atomize_workbench_declared_frames,
    atomize_workbench_response_digest,
)
from memcommit.interfaces.tui.operations.atomize.screen import (
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.commands.command_progress import (
    CommandProgress,
    progressing_provider_factory,
)
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import (
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
)
from memcommit.commands.impact_sessions import ImpactSessionPresentation
from memcommit.interfaces.tui.workbenches.review import ReviewCancelled
from memcommit.commands.session_picker import (
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.commands.update_render import (
    render_plan,
    run_update_workbench,
)
from memcommit.derived_policy import authorize_derived_transfer
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
from memcommit.study_prewarm.registry import StudyPrewarmRegistryError
from memcommit.update import UpdateError, plan_update, session_matches
from memcommit.update_endpoints import resolve_update_endpoints


class ImpactOperation(str, Enum):
    """Operation-owned artifacts supported by the Impact command."""

    atomize = "atomize"
    meld = "meld"
    sever = "sever"
    update = "update"


def _resolve_directional_access(
    store: MemoryStore,
    name: str,
    *,
    current_name: str | None,
):
    try:
        return resolve_context_access(
            store,
            name,
            current_name=current_name,
            required_permission="READ",
        )
    except ProfileError as error:
        if "does not exist" not in str(error):
            raise
        raise FileNotFoundError(f"Context '{name}' not found.") from error


def _usage_error(message: str) -> None:
    typer.secho(f"Impact error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(2)


def _select_saved_session(
    entries: tuple[SessionPickerEntry, ...],
    *,
    kind: str,
    title: str,
    session_uid: str | None,
) -> SessionPickerEntry | None:
    """Resolve an exact saved operation artifact or one frozen TTY choice."""

    if session_uid is not None:
        matches = [entry for entry in entries if entry.key == session_uid]
        if len(matches) != 1:
            raise ValueError(
                f"Saved {kind.title()} Impact artifact '{session_uid}' is not "
                "available."
            )
        return matches[0]
    if not entries:
        raise ValueError(f"No saved {kind.title()} Impact artifacts are available.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        if len(entries) == 1:
            return entries[0]
        raise ValueError(
            f"Several saved {kind.title()} artifacts are available; pass "
            "--session UID."
        )
    receipt = choose_session(entries, title=title)
    if receipt is None:
        return None
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != kind:
        raise ValueError("Impact session picker returned an invalid receipt.")
    selected = next((entry for entry in entries if entry.key == receipt.key), None)
    if selected is None or selected.reopen_argv != receipt.argv:
        raise ValueError("Impact session picker returned a stale receipt.")
    return selected


def _show_saved_impact(presentation, *, kind: str) -> bool:
    from memcommit.commands.impact_sessions import (
        render_impact_session_snapshot,
        run_impact_session_workbench,
    )

    if sys.stdin.isatty() and sys.stdout.isatty():
        handoff = run_impact_session_workbench(
            presentation,
            terminal_label=f"Interactive saved {kind.title()} Impact",
        )
        if not handoff:
            typer.echo(f"{kind.title()} Impact closed; session unchanged.")
        return handoff
    typer.echo(render_impact_session_snapshot(presentation))
    return False


def _run_saved_impact_handoff_loop(
    *,
    load_presentation: Callable[[], ImpactSessionPresentation],
    open_owning_workflow: Callable[[], None],
    kind: str,
) -> None:
    """Return a cancelled final Apply to its exact saved Impact surface."""

    while True:
        presentation = load_presentation()
        if not _show_saved_impact(presentation, kind=kind):
            return
        open_owning_workflow()
        refreshed = load_presentation()
        if not refreshed.handoff_available:
            return


def _saved_update_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
) -> None:
    from memcommit.commands.impact_sessions import update_impact_presentation

    session = store.load_staged_update() or store.load_impact_plan()
    if session is None:
        raise ValueError(
            "No saved Update or directional Impact plan exists. Run "
            "'mem impact --from SOURCE --to TARGET' first."
        )
    if session_uid is not None and session.uid != session_uid:
        raise ValueError(
            f"Saved Update Impact artifact '{session_uid}' is not available."
        )
    def load_presentation() -> ImpactSessionPresentation:
        current = store.load_staged_update() or store.load_impact_plan()
        if current is None or current.uid != session.uid:
            raise ValueError(
                "The saved Update changed while returning from Apply. Reopen it."
            )
        return update_impact_presentation(current)

    def open_owning_workflow() -> None:
        # Re-enter through Update's public command boundary so the exact live
        # endpoints, grants, operation digest, and final Apply confirmation are
        # checked again after leaving this immutable Impact projection.
        from memcommit.commands.update import cmd as update_cmd

        update_cmd(
            source_name=session.source_name,
            target_name=session.target_name,
            replace_stage=False,
            source_descendants=session.source_include_descendants,
            target_descendants=session.target_include_descendants,
        )

    _run_saved_impact_handoff_loop(
        load_presentation=load_presentation,
        open_owning_workflow=open_owning_workflow,
        kind="update",
    )


def _saved_meld_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
) -> None:
    from memcommit.commands.impact_sessions import meld_impact_presentation
    from memcommit.commands.meld_sessions import (
        list_meld_session_catalog,
        reload_selected_meld_session,
    )

    catalog = list_meld_session_catalog(store)
    by_session_uid = {entry.session_uid: entry for entry in catalog}
    entries = tuple(
        SessionPickerEntry(
            kind="meld",
            key=entry.session_uid,
            title=entry.title,
            status=entry.status,
            subtitle=entry.subtitle,
            group=entry.group,
            sort_timestamp=entry.modified_timestamp,
            detail=entry.detail,
            reopen_argv=entry.reopen_argv,
        )
        for entry in catalog
    )
    selected = _select_saved_session(
        entries,
        kind="meld",
        title="MEM IMPACT · MELD SESSIONS",
        session_uid=session_uid,
    )
    if selected is None:
        typer.echo("Meld Impact selection cancelled.")
        return
    active_entry = {"value": by_session_uid[selected.key]}

    def load_presentation() -> ImpactSessionPresentation:
        refreshed_catalog = list_meld_session_catalog(store)
        refreshed = next(
            (
                entry
                for entry in refreshed_catalog
                if entry.session_uid == selected.key
            ),
            None,
        )
        if refreshed is None:
            raise ValueError(
                "The saved Meld changed while returning from Apply. Reopen it."
            )
        active_entry["value"] = refreshed
        return meld_impact_presentation(
            reload_selected_meld_session(store, refreshed)
        )

    def open_owning_workflow() -> None:
        # The owning resume route reloads the catalog identity and enforces its
        # source/target binding checks before presenting the real Apply action.
        from memcommit.commands.meld import _resume_picked_meld

        _resume_picked_meld(
            store=store,
            entry=active_entry["value"],
        )

    _run_saved_impact_handoff_loop(
        load_presentation=load_presentation,
        open_owning_workflow=open_owning_workflow,
        kind="meld",
    )


def _saved_sever_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
) -> None:
    from memcommit.commands.impact_sessions import sever_impact_presentation
    from memcommit.commands.sever_sessions import (
        list_sever_session_catalog,
        reload_selected_sever_session,
    )
    from memcommit.sever_store import SeverSessionStore

    sessions = SeverSessionStore(store)
    catalog = list_sever_session_catalog(sessions)
    selected = _select_saved_session(
        tuple(entry.picker_entry for entry in catalog),
        kind="sever",
        title="MEM IMPACT · SEVER SESSIONS",
        session_uid=session_uid,
    )
    if selected is None:
        typer.echo("Sever Impact selection cancelled.")
        return
    active_session = {"value": None}
    owning_opened = {"value": False}

    def load_presentation() -> ImpactSessionPresentation:
        refreshed_catalog = list_sever_session_catalog(sessions)
        refreshed = next(
            (
                entry
                for entry in refreshed_catalog
                if entry.picker_entry.key == selected.key
            ),
            None,
        )
        if refreshed is None:
            raise ValueError(
                "The saved Sever changed while returning from Apply. Reopen it."
            )
        current = reload_selected_sever_session(sessions, refreshed)
        active_session["value"] = current
        return sever_impact_presentation(current)

    def open_owning_workflow() -> None:
        # Sever retains its ordinary reviewed materialization path; Impact does
        # not bypass its destination validation, CAS save, or Source boundary.
        from memcommit.commands.sever import _run_workbench

        session = active_session["value"]
        if session is None:
            raise ValueError("The saved Sever session is unavailable.")
        owning_opened["value"] = True
        active_session["value"] = _run_workbench(store, session)

    _run_saved_impact_handoff_loop(
        load_presentation=load_presentation,
        open_owning_workflow=open_owning_workflow,
        kind="sever",
    )

    final_session = active_session["value"]
    if owning_opened["value"] and final_session is not None:
        from memcommit.commands.sever import render_sever

        typer.echo(render_sever(final_session))
        typer.secho(f"Session · {final_session.uid}", fg=typer.colors.CYAN)


def _operation_session_impact(
    *,
    operation: ImpactOperation,
    session_uid: str | None,
) -> None:
    try:
        store = MemoryStore(create=False)
        runners = {
            ImpactOperation.meld: _saved_meld_impact,
            ImpactOperation.sever: _saved_sever_impact,
            ImpactOperation.update: _saved_update_impact,
        }
        runners[operation](store, session_uid=session_uid)
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


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
        source_access = _resolve_directional_access(
            store,
            endpoints.source_name,
            current_name=current_name,
        )
        target_access = _resolve_directional_access(
            store,
            endpoints.target_name,
            current_name=current_name,
        )
        authorize_derived_transfer(source_access, target_access)
        source = (
            GrantedReadStore(source_access).load(source_access.display_name)
            if source_access.is_granted
            else store.load(source_access.context_name)
        )
        target = (
            GrantedReadStore(target_access).load(target_access.display_name)
            if target_access.is_granted
            else store.load(target_access.context_name)
        )
        granted_source = (
            freeze_granted_context_binding(source_access)
            if source_access.is_granted
            else None
        )
        granted_target = (
            freeze_granted_context_binding(target_access)
            if target_access.is_granted
            else None
        )
        from memcommit.study_prewarm.update import (
            find_installed_projectable_update_prewarm,
        )

        update_prewarm_match = find_installed_projectable_update_prewarm(
            store=store,
            source=source,
            target=target,
            source_include_descendants=True,
            target_include_descendants=True,
            granted_source=granted_source,
            granted_target=granted_target,
        )
        if update_prewarm_match is not None:
            session = update_prewarm_match.session.with_status("impact")
            label = update_prewarm_match.origin.replace("_", " ")
            typer.echo(
                f"{label} · UPDATE IMPACT MATERIALIZED · provider was not called."
            )
        else:
            with CommandProgress(
                "IMPACT UPDATE",
                "connecting provider",
                total=2,
            ) as progress:
                # Live planning authenticates the provider before opening any
                # authority-owned content for disclosure. Hidden receipts need
                # no provider connection and remain within local authority.
                provider = connect_codex_chatgpt_provider()
                progress.update("planning memory changes", step=2)
                session = plan_update(
                    source,
                    target,
                    lambda: provider,
                    status="impact",
                    granted_source=granted_source,
                    granted_target=granted_target,
                )

        # Provider latency is not an authorization lease. Re-resolve both
        # endpoints and rebuild both projections before publishing the plan.
        with authority_grant_snapshot_lock() as registry:
            current_source_access = resolve_context_access(
                store,
                endpoints.source_name,
                current_name=current_name,
                required_permission="READ",
                registry=registry,
            )
            current_target_access = resolve_context_access(
                store,
                endpoints.target_name,
                current_name=current_name,
                required_permission="READ",
                registry=registry,
            )
            current_source = (
                GrantedReadStore(
                    current_source_access,
                    registry=registry,
                ).load(current_source_access.display_name)
                if current_source_access.is_granted
                else store.load(current_source_access.context_name)
            )
            current_target = (
                GrantedReadStore(
                    current_target_access,
                    registry=registry,
                ).load(current_target_access.display_name)
                if current_target_access.is_granted
                else store.load(current_target_access.context_name)
            )
            current_granted_source = (
                freeze_granted_context_binding(current_source_access)
                if current_source_access.is_granted
                else None
            )
            current_granted_target = (
                freeze_granted_context_binding(current_target_access)
                if current_target_access.is_granted
                else None
            )
            if not session_matches(
                session,
                current_source,
                current_target,
                granted_source=current_granted_source,
                granted_target=current_granted_target,
            ):
                raise UpdateError(
                    "An update endpoint or grant changed while planning; "
                    "no preview was saved."
                )
            store.save_impact_plan(session)
            if update_prewarm_match is not None:
                from memcommit.study_prewarm.update import (
                    record_equivalent_update_prewarm,
                    record_exact_update_prewarm,
                    record_projected_update_prewarm,
                )

                recorder = (
                    record_exact_update_prewarm
                    if update_prewarm_match.origin == "EXACT_PREWARM"
                    else record_equivalent_update_prewarm
                    if update_prewarm_match.origin
                    == "EQUIVALENT_SCOPE_PREWARM"
                    else record_projected_update_prewarm
                )
                recorder(
                    store,
                    entry_key=update_prewarm_match.entry_key,
                    session=session,
                    prepared_source_name=(
                        update_prewarm_match.prepared_source_name
                    ),
                )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        StudyPrewarmRegistryError,
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
                    allow_prepared=not refresh and not with_review,
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
            help=(
                "Impact operation: atomize, meld, sever, or update; omit for "
                "a directional Update preview"
            ),
        ),
    ] = None,
    session_uid: Annotated[
        Optional[str],
        typer.Option(
            "--session",
            help="Exact saved Meld, Sever, or Update artifact uid",
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
    """Preview a new plan or inspect saved Impact before an optional Apply handoff."""
    if operation is ImpactOperation.atomize:
        if session_uid is not None:
            _usage_error(
                "'--session' is valid only with 'mem impact meld', "
                "'mem impact sever', or 'mem impact update'."
            )
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

    if operation is not None:
        if (
            source_name is not None
            or target_name is not None
            or context_name is not None
            or show_all
            or with_review
            or refresh
        ):
            _usage_error(
                f"'mem impact {operation.value}' opens a saved session and "
                "cannot be combined with directional or atomize options."
            )
        _operation_session_impact(
            operation=operation,
            session_uid=session_uid,
        )
        return

    if source_name is None and target_name is None:
        _usage_error(
            "choose an endpoint with '--from SOURCE' or '--to TARGET', "
            "preview atomization with 'mem impact atomize', or inspect a "
            "saved 'meld', 'sever', or 'update' Impact."
        )
    if (
        session_uid is not None
        or context_name is not None
        or show_all
        or with_review
        or refresh
    ):
        _usage_error(
            "'--session' is valid only with a saved-session operation; "
            "'--context', '--all', '--with-review', and '--refresh' are only "
            "valid with 'mem impact atomize'."
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
