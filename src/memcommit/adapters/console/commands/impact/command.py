"""Preview new effects or inspect saved operation-owned Impact artifacts."""

from __future__ import annotations

import sys
from collections.abc import Callable
from enum import Enum
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.shared.command_group import CanonicalCommandGroup

from memcommit.application.operations.atomize.domain import (
    AtomizeFrameOrigin,
    AtomizeImpactError,
    atomize_analysis_matches_context,
)
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisApplicationError,
    AtomizeAnalysisOpenRequest,
)
from memcommit.application.operations.atomize.analysis_runtime import (
    execute_atomize_analysis_open,
)
from memcommit.application.operations.atomize.workbench import (
    AtomizeWorkbenchError,
    atomize_workbench_declared_frames,
    atomize_workbench_response_digest,
)
from memcommit.adapters.interfaces.tui.operations.atomize.screen import (
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.adapters.console.commands.shared.command_progress import (
    CommandProgress,
    progressing_provider_factory,
)
from memcommit.adapters.console.commands.shared.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.application.authority.access import (
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
)
from memcommit.adapters.console.commands.impact.sessions import ImpactSessionPresentation
from memcommit.adapters.console.commands.impact.catalog import choose_impact_session
from memcommit.adapters.console.commands.impact.process_local import (
    distill_cmd as distill_impact_cmd,
    elaborate_cmd as elaborate_impact_cmd,
    forget_cmd as forget_impact_cmd,
    resolve_cmd as resolve_impact_cmd,
)
from memcommit.adapters.interfaces.cli.impact_registry import IMPACT_ROUTES
from memcommit.adapters.interfaces.tui.workbenches.review import ReviewCancelled
from memcommit.adapters.interfaces.tui.components.operation_launcher.session import (
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.adapters.console.text import (
    display_escape_text,
)
from memcommit.adapters.console.commands.update.render import (
    render_plan,
    run_update_workbench,
)
from memcommit.core.context_targeting.loading import (
    DirectMemoryAmbiguityError,
    load_context_scope,
    resolve_local_context_memory_target,
)
from memcommit.core.context_targeting.memory_focus import is_memory_uid_prefix
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryLocator,
    DirectMemoryTarget,
    ExistingContextOperand,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.core.context_targeting.presets import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.application.authority.derived_policy import authorize_derived_transfer
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.review.model import (
    ReviewError,
    atomize_review_declared_frames,
    atomize_review_matches_analysis,
    review_response_digest,
)
from memcommit.persistence.store import MemoryStore
from memcommit.core.context_targeting.uid_locator import (
    UidLocatorError,
    resolve_exact_or_unique_uid,
)
from memcommit.study_scenarios.legacy.prewarm.registry import StudyPrewarmRegistryError
from memcommit.application.operations.update.model import (
    UpdateError,
    plan_update,
    session_matches,
)
from memcommit.application.operations.update.endpoints import (
    choose_update_endpoint_operands,
    resolve_update_endpoints,
)


app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help=(
        "Preview operation-owned effects without applying them, or omit the "
        "operation for a directional Update preview."
    ),
)


class ImpactOperation(str, Enum):
    """Internal discriminator used by the legacy dispatcher behind the registry."""

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
    """Resolve one saved UID/prefix or one frozen TTY choice."""

    if session_uid is not None:
        try:
            return resolve_exact_or_unique_uid(
                entries,
                session_uid,
                uid=lambda entry: entry.key,
                label=f"Saved {kind.title()} Impact artifact",
            )
        except UidLocatorError as error:
            raise ValueError(str(error)) from error
    if not entries:
        raise ValueError(f"No saved {kind.title()} Impact artifacts are available.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        if len(entries) == 1:
            return entries[0]
        raise ValueError(
            f"Several saved {kind.title()} artifacts are available; pass --session UID."
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
    from memcommit.adapters.console.commands.impact.sessions import (
        render_impact_session_snapshot,
        run_impact_session_workbench,
    )

    if sys.stdin.isatty() and sys.stdout.isatty():
        handoff = run_impact_session_workbench(
            presentation,
            terminal_label=f"Interactive saved {kind.title()} Impact",
        )
        if not handoff:
            typer.echo(f"{kind.title()} Impact closed.")
        return handoff
    typer.echo(render_impact_session_snapshot(presentation))
    return False


def _saved_atomize_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
    show_all: bool = False,
) -> None:
    """Open one exact Atomize analysis without a create or refresh fallback."""

    from memcommit.adapters.console.commands.atomize.sessions import (
        load_saved_atomize_analysis,
        revalidate_saved_atomize_analysis,
    )

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
    from memcommit.adapters.console.commands.impact.sessions import update_impact_presentation
    from memcommit.application.operations.update.receipt_store import UpdateReceiptStore

    current = store.load_staged_update() or store.load_impact_plan()
    receipts = UpdateReceiptStore(store)
    retained = receipts.list()
    if current is None and not retained:
        raise ValueError(
            "No saved Update or directional Impact plan exists. Run "
            "'mem impact --from SOURCE --to TARGET' first."
        )
    retained_uids = {candidate.uid for candidate in retained}
    if session_uid is None:
        session = current or retained[0]
    else:
        candidates = retained
        if current is not None and current.uid not in retained_uids:
            candidates = (*retained, current)
        session = resolve_exact_or_unique_uid(
            candidates,
            session_uid,
            uid=lambda candidate: candidate.uid,
            label="Saved Update Impact artifact",
        )
    selected_is_retained = session.uid in retained_uids

    def load_presentation() -> ImpactSessionPresentation:
        if selected_is_retained:
            return update_impact_presentation(receipts.load(session.uid))
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
        from memcommit.adapters.console.commands.update.command import cmd as update_cmd

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
    from memcommit.adapters.console.commands.impact.sessions import meld_impact_presentation
    from memcommit.adapters.console.commands.meld.sessions import (
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
            (entry for entry in refreshed_catalog if entry.session_uid == selected.key),
            None,
        )
        if refreshed is None:
            raise ValueError(
                "The saved Meld changed while returning from Apply. Reopen it."
            )
        active_entry["value"] = refreshed
        return meld_impact_presentation(reload_selected_meld_session(store, refreshed))

    def open_owning_workflow() -> None:
        # The owning resume route reloads the catalog identity and enforces its
        # source/target binding checks before presenting the real Apply action.
        from memcommit.adapters.console.commands.meld.command import _resume_picked_meld

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
    from memcommit.adapters.console.commands.impact.sessions import sever_impact_presentation
    from memcommit.adapters.console.commands.sever.sessions import (
        list_sever_session_catalog,
        reload_selected_sever_session,
    )
    from memcommit.application.operations.sever.session_store import SeverSessionStore

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
        from memcommit.adapters.console.commands.sever.command import _run_workbench

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
        from memcommit.adapters.console.commands.sever.command import render_sever

        typer.echo(render_sever(final_session))
        typer.secho(f"Session · {final_session.uid}", fg=typer.colors.CYAN)


def _operation_session_impact(
    *,
    operation: ImpactOperation,
    session_uid: str | None,
    show_all: bool = False,
) -> None:
    try:
        store = MemoryStore(create=False)
        runners = {
            ImpactOperation.meld: _saved_meld_impact,
            ImpactOperation.sever: _saved_sever_impact,
            ImpactOperation.update: _saved_update_impact,
        }
        if operation is ImpactOperation.atomize:
            _saved_atomize_impact(
                store,
                session_uid=session_uid,
                show_all=show_all,
            )
        else:
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


def _browse_impact_sessions(
    *,
    operation: ImpactOperation | None = None,
    show_all: bool = False,
) -> None:
    """Select a durable Impact artifact, then enter its exact saved route."""

    try:
        store = MemoryStore(create=False)
        receipt = choose_impact_session(
            store,
            kinds=None if operation is None else (operation.value,),
            title=(
                "MEM IMPACT · SAVED ANALYSES"
                if operation is None
                else f"MEM IMPACT · {operation.value.upper()} ANALYSES"
            ),
        )
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if receipt is None:
        typer.echo("Impact selection cancelled; no analysis was opened.")
        return
    _operation_session_impact(
        operation=ImpactOperation(receipt.kind),
        session_uid=receipt.key,
        show_all=show_all,
    )


def _directional_impact(
    *,
    store: MemoryStore,
    current_name: str | None,
    source_name: str | None,
    target_name: str | None,
    source_memory: str | None = None,
    target_memory: str | None = None,
    source_descendants: bool = False,
    target_descendants: bool = False,
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
        source_store = (
            GrantedReadStore(source_access) if source_access.is_granted else store
        )
        target_store = (
            GrantedReadStore(target_access) if target_access.is_granted else store
        )
        source = load_context_scope(
            source_store,
            (
                source_access.display_name
                if source_access.is_granted
                else source_access.context_name
            ),
            include_descendants=source_descendants,
        )
        target = load_context_scope(
            target_store,
            (
                target_access.display_name
                if target_access.is_granted
                else target_access.context_name
            ),
            include_descendants=target_descendants,
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
        from memcommit.study_scenarios.legacy.prewarm.update import (
            find_installed_projectable_update_prewarm,
        )

        update_prewarm_match = (
            None
            if source_memory is not None or target_memory is not None
            else find_installed_projectable_update_prewarm(
                store=store,
                source=source,
                target=target,
                source_include_descendants=source_descendants,
                target_include_descendants=target_descendants,
                granted_source=granted_source,
                granted_target=granted_target,
            )
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
                progress.update("planning memory changes", step=2)
                session = plan_update(
                    source,
                    target,
                    # Keep connection lazy so Update's complete authority and
                    # semantic-disclosure preflight runs first. A nested live
                    # Grant must fail without contacting a provider at all.
                    connect_codex_chatgpt_provider,
                    status="impact",
                    source_include_descendants=source_descendants,
                    target_include_descendants=target_descendants,
                    granted_source=granted_source,
                    granted_target=granted_target,
                    source_memory_selector=source_memory,
                    target_memory_selector=target_memory,
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
            current_source_store = (
                GrantedReadStore(
                    current_source_access,
                    registry=registry,
                )
                if current_source_access.is_granted
                else store
            )
            current_target_store = (
                GrantedReadStore(
                    current_target_access,
                    registry=registry,
                )
                if current_target_access.is_granted
                else store
            )
            current_source = load_context_scope(
                current_source_store,
                (
                    current_source_access.display_name
                    if current_source_access.is_granted
                    else current_source_access.context_name
                ),
                include_descendants=source_descendants,
            )
            current_target = load_context_scope(
                current_target_store,
                (
                    current_target_access.display_name
                    if current_target_access.is_granted
                    else current_target_access.context_name
                ),
                include_descendants=target_descendants,
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
                from memcommit.study_scenarios.legacy.prewarm.update import (
                    record_equivalent_update_prewarm,
                    record_exact_update_prewarm,
                    record_projected_update_prewarm,
                )

                recorder = (
                    record_exact_update_prewarm
                    if update_prewarm_match.origin == "EXACT_PREWARM"
                    else record_equivalent_update_prewarm
                    if update_prewarm_match.origin == "EQUIVALENT_SCOPE_PREWARM"
                    else record_projected_update_prewarm
                )
                recorder(
                    store,
                    entry_key=update_prewarm_match.entry_key,
                    session=session,
                    prepared_source_name=(update_prewarm_match.prepared_source_name),
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


def _dispatch_impact(
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
            help="Saved Meld, Sever, or Update artifact uid or unique prefix",
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Browse saved Impact analyses in an interactive launcher",
        ),
    ] = False,
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
    source_memory: Annotated[
        Optional[str],
        typer.Option(
            "--source-memory",
            metavar="UID_OR_PREFIX",
            help="With directional Update, focus one Source Memory",
        ),
    ] = None,
    target_memory: Annotated[
        Optional[str],
        typer.Option(
            "--target-memory",
            metavar="UID_OR_PREFIX",
            help="With directional Update, focus one Target Memory",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only explicit directional Update endpoint roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both directional Update endpoints",
        ),
    ] = False,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Refine directional Update Source reach",
        ),
    ] = None,
    target_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--target-descendants/--target-root-only",
            legacy_root_only_option_alias("target"),
            help="Refine directional Update Target reach",
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
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            metavar="UID_OR_PREFIX",
            help=(
                "With atomize, analyze one direct Memory while its neighbors "
                "remain non-actionable context"
            ),
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
    auto_context_memory_operand: str | None = None,
) -> None:
    """Preview a new plan or inspect saved Impact before an optional Apply handoff."""
    scope_flags_supplied = (
        direct
        or recursive
        or source_descendants is not None
        or target_descendants is not None
    )
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        source_descendants, target_descendants = resolve_descendant_scopes(
            preset=preset,
            explicit=(source_descendants, target_descendants),
        )
    except (TypeError, ValueError) as error:
        _usage_error(str(error))
    if operation is ImpactOperation.atomize:
        if scope_flags_supplied:
            _usage_error(
                "Context scope presets apply to directional Update Impact; "
                "atomize remains direct-only."
            )
        if sessions and session_uid is not None:
            _usage_error(
                "use either '--sessions' to browse saved Atomize analyses or "
                "'--session UID' to reopen one exact analysis."
            )
        if sessions or session_uid is not None:
            if (
                source_name is not None
                or target_name is not None
                or context_name is not None
                or memory_selector is not None
                or auto_context_memory_operand is not None
                or source_memory is not None
                or target_memory is not None
                or with_review
                or refresh
            ):
                _usage_error(
                    "saved Atomize Impact selection cannot be combined with "
                    "Context, Memory, directional, or reanalysis options."
                )
            if sessions:
                _browse_impact_sessions(
                    operation=ImpactOperation.atomize,
                    show_all=show_all,
                )
            else:
                _operation_session_impact(
                    operation=ImpactOperation.atomize,
                    session_uid=session_uid,
                    show_all=show_all,
                )
            return
        if source_name is not None or target_name is not None:
            _usage_error(
                "'atomize' cannot be combined with '--from' or '--to'. "
                "Use either 'mem impact atomize' or "
                "a directional 'mem impact --from SOURCE' / "
                "'--to TARGET' form."
            )
        if source_memory is not None or target_memory is not None:
            _usage_error(
                "'--source-memory' and '--target-memory' select directional "
                "Update inputs, not atomize inputs; use '--memory' for atomize."
            )
        try:
            store = MemoryStore(create=False)
            context_snapshot = ContextOperandSnapshot.capture(store)
            if auto_context_memory_operand is not None:
                auto_target = resolve_local_context_memory_target(
                    store,
                    auto_context_memory_operand,
                    current=context_snapshot.current_name,
                )
                canonical_context_name = auto_target.context_name
                if isinstance(auto_target, DirectMemoryTarget):
                    memory_selector = auto_target.memory_uid
                else:
                    assert isinstance(auto_target, ContextTarget)
            else:
                canonical_context_name = context_snapshot.resolve_or_current(
                    context_name
                )
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
            memory_selector=memory_selector,
        )
        return

    if operation is not None:
        if (
            source_name is not None
            or target_name is not None
            or context_name is not None
            or memory_selector is not None
            or source_memory is not None
            or target_memory is not None
            or show_all
            or with_review
            or refresh
            or sessions
            or scope_flags_supplied
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
        or sessions
        or context_name is not None
        or memory_selector is not None
        or show_all
        or with_review
        or refresh
    ):
        _usage_error(
            "'--session' and '--sessions' require a saved-session operation; "
            "'--context', '--memory', '--all', '--with-review', and '--refresh' are only "
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
        source_memory=source_memory,
        target_memory=target_memory,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
    )


@app.callback(invoke_without_command=True)
def cmd(
    ctx: typer.Context,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Source Context A; if --to is omitted, current supplies B",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Target Context B; if --from is omitted, current supplies A",
        ),
    ] = None,
    source_memory: Annotated[
        Optional[str],
        typer.Option(
            "--source-memory",
            metavar="UID_OR_PREFIX",
            help="Focus one Source Memory",
        ),
    ] = None,
    target_memory: Annotated[
        Optional[str],
        typer.Option(
            "--target-memory",
            metavar="UID_OR_PREFIX",
            help="Focus one Target Memory",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Use only explicit endpoint roots"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both endpoints",
        ),
    ] = False,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Refine Source reach",
        ),
    ] = None,
    target_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--target-descendants/--target-root-only",
            legacy_root_only_option_alias("target"),
            help="Refine Target reach",
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Browse every saved analysis inspectable through Impact",
        ),
    ] = False,
) -> None:
    """Preview directional Update effects when no named operation is supplied."""

    directional_options = (
        source_name is not None
        or target_name is not None
        or source_memory is not None
        or target_memory is not None
        or direct
        or recursive
        or source_descendants is not None
        or target_descendants is not None
    )
    if ctx.invoked_subcommand is not None:
        if directional_options:
            _usage_error(
                "directional Update options cannot be combined with a named "
                "Impact operation."
            )
        if sessions:
            _usage_error(
                "root '--sessions' cannot be combined with a named Impact "
                "operation; put operation-specific options after its name."
            )
        return
    if sessions:
        if directional_options:
            _usage_error(
                "'--sessions' cannot be combined with directional Update "
                "endpoints or reach options."
            )
        _browse_impact_sessions()
        return
    _dispatch_impact(
        operation=None,
        source_name=source_name,
        target_name=target_name,
        source_memory=source_memory,
        target_memory=target_memory,
        direct=direct,
        recursive=recursive,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
    )


def atomize_impact_cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="TARGET",
            help=(
                "Auto-typed existing Context, Memory UID/prefix, or "
                "CONTEXT:UID (defaults to current Context)"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to analyze (defaults to current)",
        ),
    ] = None,
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            metavar="UID_OR_PREFIX",
            help="Analyze one direct Memory with its neighbors as context",
        ),
    ] = None,
    show_all: Annotated[
        bool,
        typer.Option("--all", help="Include unchanged ATOMIC Memories"),
    ] = False,
    with_review: Annotated[
        bool,
        typer.Option(
            "--with-review",
            help="Reanalyze using saved unary workbench responses",
        ),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Replace the saved analysis with a new semantic completion",
        ),
    ] = False,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Browse saved Atomize analyses in the Impact launcher",
        ),
    ] = False,
    session_uid: Annotated[
        Optional[str],
        typer.Option(
            "--session",
            help="Saved Atomize analysis uid or unambiguous prefix",
        ),
    ] = None,
) -> None:
    """Preview one Context's exhaustive Atomize classification and splits."""

    try:
        parsed_operand = (
            parse_auto_typed_context_memory_operand(context_operand)
            if context_operand is not None
            else None
        )
        if (
            isinstance(parsed_operand, ExistingContextOperand)
            and context_name is None
            and is_memory_uid_prefix(context_operand)
        ):
            early_store = MemoryStore(create=False)
            early_snapshot = ContextOperandSnapshot.capture(early_store)
            try:
                early_target = resolve_local_context_memory_target(
                    early_store,
                    context_operand,
                    current=early_snapshot.current_name,
                )
            except FileNotFoundError:
                early_target = None
            except DirectMemoryAmbiguityError:
                # Keep this in Memory mode so duplicate options and saved-
                # session conflicts are rejected before the runtime replays
                # the complete ambiguity diagnostic.
                parsed_operand = DirectMemoryLocator(context_operand)
                early_target = None
            if isinstance(early_target, DirectMemoryTarget):
                parsed_operand = DirectMemoryLocator(
                    early_target.memory_uid,
                    early_target.context_name,
                )
        if isinstance(parsed_operand, DirectMemoryLocator):
            if context_name is not None:
                raise ValueError(
                    "Auto-typed Memory cannot be combined with --context; use "
                    "CONTEXT:UID or --context CONTEXT --memory UID."
                )
            if memory_selector is not None:
                raise ValueError(
                    "Memory was supplied both positionally and with --memory."
                )
            context_name = parsed_operand.context_locator
            memory_selector = parsed_operand.memory_selector
        else:
            context_name = choose_context_operand(
                (
                    parsed_operand.locator
                    if isinstance(parsed_operand, ExistingContextOperand)
                    else None
                ),
                option=context_name,
            )
    except ValueError as error:
        _usage_error(str(error))

    _dispatch_impact(
        operation=ImpactOperation.atomize,
        session_uid=session_uid,
        sessions=sessions,
        context_name=context_name,
        memory_selector=memory_selector,
        auto_context_memory_operand=context_operand,
        show_all=show_all,
        with_review=with_review,
        refresh=refresh,
    )


def _saved_impact_cmd(operation: ImpactOperation, session_uid: str | None) -> None:
    _dispatch_impact(operation=operation, session_uid=session_uid)


def meld_impact_cmd(
    session_uid: Annotated[
        Optional[str],
        typer.Option("--session", help="Saved Meld artifact uid or unique prefix"),
    ] = None,
) -> None:
    """Inspect one exact saved Meld assessment."""

    _saved_impact_cmd(ImpactOperation.meld, session_uid)


def sever_impact_cmd(
    session_uid: Annotated[
        Optional[str],
        typer.Option("--session", help="Saved Sever artifact uid or unique prefix"),
    ] = None,
) -> None:
    """Inspect one exact saved Sever result."""

    _saved_impact_cmd(ImpactOperation.sever, session_uid)


def update_impact_cmd(
    contexts: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="SOURCE TARGET",
            help="Explicit Source and Target Contexts for a new preview",
        ),
    ] = None,
    session_uid: Annotated[
        Optional[str],
        typer.Option("--session", help="Saved Update artifact uid or unique prefix"),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Source Context; current supplies Target when --to is omitted",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Target Context; current supplies Source when --from is omitted",
        ),
    ] = None,
    source_memory: Annotated[
        Optional[str],
        typer.Option(
            "--source-memory",
            metavar="UID_OR_PREFIX",
            help="Focus one Source Memory",
        ),
    ] = None,
    target_memory: Annotated[
        Optional[str],
        typer.Option(
            "--target-memory",
            metavar="UID_OR_PREFIX",
            help="Focus one Target Memory",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Use only explicit endpoint roots"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both endpoints",
        ),
    ] = False,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Refine Source reach",
        ),
    ] = None,
    target_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--target-descendants/--target-root-only",
            legacy_root_only_option_alias("target"),
            help="Refine Target reach",
        ),
    ] = None,
) -> None:
    """Preview a directional Update or inspect one saved Update plan."""

    try:
        source_name, target_name = choose_update_endpoint_operands(
            contexts,
            source_option=source_name,
            target_option=target_name,
        )
    except ValueError as error:
        _usage_error(str(error))

    planning_requested = (
        source_name is not None
        or target_name is not None
        or source_memory is not None
        or target_memory is not None
        or direct
        or recursive
        or source_descendants is not None
        or target_descendants is not None
    )
    if session_uid is not None and planning_requested:
        _usage_error(
            "--session cannot be combined with a new directional Update preview."
        )
    if not planning_requested:
        _saved_impact_cmd(ImpactOperation.update, session_uid)
        return

    _dispatch_impact(
        operation=None,
        source_name=source_name,
        target_name=target_name,
        source_memory=source_memory,
        target_memory=target_memory,
        direct=direct,
        recursive=recursive,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
    )


# Registry installation is deliberately last: every public named route must
# have exactly one operation adapter, while the callback remains the separate
# directional Update form.
IMPACT_ROUTES.install(
    app,
    {
        "atomize": atomize_impact_cmd,
        "forget": forget_impact_cmd,
        "distill": distill_impact_cmd,
        "elaborate": elaborate_impact_cmd,
        "resolve": resolve_impact_cmd,
        "meld": meld_impact_cmd,
        "sever": sever_impact_cmd,
        "update": update_impact_cmd,
    },
)
