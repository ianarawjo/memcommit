"""Apply or reopen a semantic update from Context A to a local target B."""

from datetime import datetime
import sys
from typing import Annotated, Optional

import typer

from memcommit.commands.command_wait import (
    CommandWaitView,
    build_report_loading_view,
    run_command_wait,
)
from memcommit.commands.endpoint_setup_flows import choose_update_setup
from memcommit.commands.granted_context import (
    GrantedReadStore,
    freeze_granted_update_target,
    resolve_context_access,
)
from memcommit.commands.session_picker import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.commands.update_render import (
    render_plan,
    render_update_report_snapshot,
    review_update_application,
)
from memcommit.context import Context
from memcommit.context_targeting.loading import load_context_scope
from memcommit.derived_policy import authorize_derived_transfer
from memcommit.granted_source_update_application import (
    apply_granted_source_staged_update,
)
from memcommit.granted_update_application import apply_granted_staged_update
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.study_prewarm.registry import StudyPrewarmRegistryError
from memcommit.update import (
    GrantedUpdateTarget,
    UpdateError,
    UpdateSession,
    applied_session_matches,
    plan_update,
    revise_update,
    session_matches,
)
from memcommit.update_endpoints import resolve_update_endpoints


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _run_saved_update_workbench(session: UpdateSession) -> bool:
    """Open the shared state-aware Update surface without eager UI imports."""

    from memcommit.commands.impact_sessions import (
        run_impact_session_workbench,
        update_impact_presentation,
    )

    return run_impact_session_workbench(
        update_impact_presentation(session),
        terminal_label="Interactive saved Update Impact",
    )


def _browse_saved_update(store: MemoryStore) -> None:
    """Browse the singleton receipt, or collect endpoints for a new Update."""
    session = store.load_staged_update()
    interactive = _interactive_terminal()
    if not interactive:
        if session is None:
            typer.echo("No saved Update session.")
        else:
            render_plan(
                session,
                staged=session.status == "staged",
                applied=session.status == "applied",
            )
        return

    entries: tuple[SessionPickerEntry, ...] = ()
    if session is not None:
        entries = (
            SessionPickerEntry(
                kind="update",
                key=session.uid,
                title=f"{session.source_name} → {session.target_name}",
                status=session.status.upper(),
                subtitle=(
                    f"{len(session.operations)} planned "
                    f"{'change' if len(session.operations) == 1 else 'changes'}"
                ),
                group=session.target_name,
                sort_timestamp=datetime.fromisoformat(session.created_at).timestamp(),
                detail=(
                    f"Session {session.uid}\n"
                    f"Source {session.source_name}\n"
                    f"Target {session.target_name}\n"
                    "Source scope "
                    f"{'includes descendants' if session.source_include_descendants else 'selected graph only'}\n"
                    "Target scope "
                    f"{'includes descendants' if session.target_include_descendants else 'selected graph only'}\n"
                    "Update retains one global receipt; New replaces it only "
                    "through the existing explicit endpoint checks."
                ),
                reopen_argv=("mem", "update"),
            ),
        )
    receipt = choose_session(
        entries,
        title="MEM UPDATE · SAVED SESSION",
        new_receipt=SessionNewReceipt(kind="update", argv=("mem", "update")),
    )
    if receipt is None:
        typer.echo("Update selection cancelled.")
        return
    if isinstance(receipt, SessionNewReceipt):
        if receipt.kind != "update" or receipt.argv != ("mem", "update"):
            raise UpdateError("Update session picker returned an invalid receipt.")
        setup = choose_update_setup(store)
        if setup is None:
            typer.echo("New Update cancelled; no session was created.")
            return
        cmd(
            source_name=setup.source_name,
            target_name=setup.target_name,
            source_descendants=setup.source_descendants,
            target_descendants=setup.target_descendants,
        )
        return
    if (
        not isinstance(receipt, SessionOpenReceipt)
        or receipt.kind != "update"
        or session is None
        or receipt.key != session.uid
        or receipt.argv != ("mem", "update")
    ):
        raise UpdateError("Update session picker returned an invalid receipt.")
    current = store.load_staged_update()
    if current is None or current.to_dict() != session.to_dict():
        raise UpdateError(
            "The saved Update session changed while the launcher was open. Reopen it."
        )
    while True:
        handoff = _run_saved_update_workbench(current)
        if not handoff:
            typer.echo("Update view closed; saved session unchanged.")
            return

        # The Impact workbench is inspection-only. Re-enter Update through its
        # public command boundary so an Apply request repeats the normal endpoint,
        # authority, freshness, and exact-review checks.
        cmd(
            source_name=current.source_name,
            target_name=current.target_name,
            replace_stage=False,
            source_descendants=current.source_include_descendants,
            target_descendants=current.target_include_descendants,
        )
        refreshed = store.load_staged_update()
        if (
            refreshed is None
            or refreshed.uid != current.uid
            or refreshed.status not in {"impact", "staged"}
        ):
            return
        # A cancelled final Apply leaves the exact staged receipt actionable.
        # Reopen its Impact screen so Back is a real stack transition rather
        # than dropping the person at the command prompt.
        current = refreshed


def _resolve_update_access(
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


def _update_confirmed_inputs_view(
    source: Context,
    target: Context,
    *,
    source_descendants: bool,
    target_descendants: bool,
    guidance: str | None = None,
) -> CommandWaitView:
    """Freeze the exact Update route shown while its semantic turn runs."""

    lines = [
        "MEM UPDATE · FROZEN INPUTS · RESULT PENDING",
        "",
        f"SOURCE A · {display_escape_text(source.name)}",
        "  SCOPE · "
        + ("INCLUDE DESCENDANTS" if source_descendants else "SELECTED GRAPH ONLY"),
        "  UPDATE EFFECT · READ-ONLY WHILE PLANNING",
        "",
        f"TARGET B · {display_escape_text(target.name)}",
        "  SCOPE · "
        + ("INCLUDE DESCENDANTS" if target_descendants else "SELECTED GRAPH ONLY"),
        "  UPDATE EFFECT · READ-ONLY UNTIL EXPLICIT APPLY",
    ]
    if guidance is not None:
        lines.extend(
            [
                "",
                "REVISION COMMENT · SUBMITTED · NOT YET INCORPORATED",
                safe_terminal_text(guidance),
            ]
        )
    lines.extend(
        [
            "",
            "No target change is applied while this report is being built.",
        ]
    )
    return CommandWaitView(
        title="UPDATE CONFIRMED INPUTS · READ-ONLY",
        text="\n".join(lines),
    )


def _update_loading_view() -> CommandWaitView:
    """Project Update's eventual report topology through shared loading chrome."""

    return build_report_loading_view(
        "UPDATE",
        sections=("Plan", "What will change", "Planned changes", "To do"),
    )


def _update_revision_wait_view(
    session: UpdateSession,
    guidance: str,
) -> CommandWaitView:
    """Keep the reviewed staged report visible until its replacement is ready."""

    text = "\n".join(
        [
            render_update_report_snapshot(session, staged=True),
            "",
            "PENDING REVISION · SUBMITTED · NOT YET INCORPORATED",
            safe_terminal_text(guidance),
        ]
    )
    return CommandWaitView(
        title="PREVIOUS UPDATE REPORT · READ-ONLY",
        text=text,
    )


def _plan_update_with_wait(
    source: Context,
    target: Context,
    *,
    source_descendants: bool,
    target_descendants: bool,
    granted_source: GrantedUpdateTarget | None,
    granted_target: GrantedUpdateTarget | None,
) -> UpdateSession:
    """Plan one complete Update while sharing the interactive command wait."""

    def plan(progress):
        def connect():
            provider = connect_codex_chatgpt_provider()
            progress.update("planning memory changes", step=2)
            return provider

        return plan_update(
            source,
            target,
            connect,
            status="staged",
            source_include_descendants=source_descendants,
            target_include_descendants=target_descendants,
            granted_source=granted_source,
            granted_target=granted_target,
        )

    return run_command_wait(
        "UPDATE",
        "connecting provider",
        total=2,
        work=plan,
        return_view=_update_loading_view(),
        context_view=_update_confirmed_inputs_view(
            source,
            target,
            source_descendants=source_descendants,
            target_descendants=target_descendants,
        ),
    )


def _revise_update_with_wait(
    current: UpdateSession,
    source: Context,
    target: Context,
    guidance: str,
) -> UpdateSession:
    """Replace a reviewed plan while retaining its frozen report and route."""

    def revise(progress):
        def connect():
            provider = connect_codex_chatgpt_provider()
            progress.update("incorporating review comments", step=2)
            return provider

        return revise_update(
            current,
            source,
            target,
            connect,
            guidance,
        )

    return run_command_wait(
        "UPDATE",
        "connecting provider",
        total=2,
        work=revise,
        return_view=_update_revision_wait_view(current, guidance),
        context_view=_update_confirmed_inputs_view(
            source,
            target,
            source_descendants=current.source_include_descendants,
            target_descendants=current.target_include_descendants,
            guidance=guidance,
        ),
    )


def cmd(
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
    replace_stage: Annotated[
        bool,
        typer.Option(
            "--replace-stage",
            help="Replace a different, stale, or applied update record",
        ),
    ] = False,
    source_descendants: Annotated[
        bool,
        typer.Option(
            "--source-descendants/--source-only",
            help="Include all readable descendant Contexts under Source A",
        ),
    ] = False,
    target_descendants: Annotated[
        bool,
        typer.Option(
            "--target-descendants/--target-only",
            help="Include all writable descendant Contexts under Target B",
        ),
    ] = False,
) -> None:
    if source_name is None and target_name is None:
        store = MemoryStore(create=False)
        try:
            _browse_saved_update(store)
        except (OSError, UpdateError, ValueError) as error:
            typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        return

    store = MemoryStore()
    try:
        # Both locators must retain the meaning they had at command start,
        # even if another process switches the global current Context later.
        current_name = store.current_context_name()
        endpoints = resolve_update_endpoints(
            source_locator=source_name,
            target_locator=target_name,
            current=current_name,
        )
        source_access = _resolve_update_access(
            store,
            endpoints.source_name,
            current_name=current_name,
        )
        target_access = _resolve_update_access(
            store,
            endpoints.target_name,
            current_name=current_name,
        )
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
            freeze_granted_update_target(source_access)
            if source_access.is_granted
            else None
        )
        granted_target = (
            freeze_granted_update_target(target_access)
            if target_access.is_granted
            else None
        )
        authorize_derived_transfer(source_access, target_access)
    except (
        FileNotFoundError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        existing = store.load_staged_update()
    except ValueError as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if existing is not None and existing.status == "applied":
        if (
            existing.source_include_descendants == source_descendants
            and existing.target_include_descendants == target_descendants
            and applied_session_matches(
                existing,
                source,
                target,
                granted_source=granted_source,
                granted_target=granted_target,
            )
        ):
            render_plan(existing, applied=True)
            typer.echo("This update was already applied locally.")
            return
        if not replace_stage:
            typer.secho(
                "Update error: an applied update or its local working copy "
                "has diverged. Review it before using '--replace-stage'.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    if existing is not None and existing.status == "undone" and not replace_stage:
        render_plan(existing, applied=False)
        typer.echo(
            "This update was undone. Run 'mem redo' to restore the exact "
            "application, or use '--replace-stage' to discard this receipt."
        )
        return

    if existing is not None and existing.status == "impact" and not replace_stage:
        typer.secho(
            "Update error: the active update record is not staged.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if existing is not None and existing.status == "staged" and not replace_stage:
        if (
            existing.source_include_descendants == source_descendants
            and existing.target_include_descendants == target_descendants
            and session_matches(
                existing,
                source,
                target,
                granted_source=granted_source,
                granted_target=granted_target,
            )
        ):
            session = existing
        else:
            typer.secho(
                "Update error: another or stale update is already staged. "
                "Review it before using '--replace-stage'.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
    else:
        session = None

    cached = None
    try:
        cached = store.load_impact_plan()
    except ValueError:
        # A malformed read-only cache is never reused. A newly validated plan
        # replaces it only after provider success.
        cached = None

    try:
        update_prewarm_match = None
        update_analysis_origin: str | None = None
        if session is not None:
            from memcommit.study_prewarm.update import (
                installed_update_prewarm_origin,
            )

            update_analysis_origin = installed_update_prewarm_origin(
                store,
                session,
            )
        if session is None:
            if (
                cached is not None
                and cached.source_include_descendants == source_descendants
                and cached.target_include_descendants == target_descendants
                and session_matches(
                    cached,
                    source,
                    target,
                    granted_source=granted_source,
                    granted_target=granted_target,
                )
            ):
                session = cached.with_status("staged")
                from memcommit.study_prewarm.update import (
                    installed_update_prewarm_origin,
                )

                origin = installed_update_prewarm_origin(store, cached)
                if origin is not None:
                    update_analysis_origin = origin
                    label = (
                        "EXACT PREWARM"
                        if origin == "EXACT_PREWARM"
                        else "PROJECTED PREWARM"
                        if origin == "PROJECTED_PREWARM"
                        else "EQUIVALENT SCOPE PREWARM"
                    )
                    typer.echo(
                        f"{label} · UPDATE PLAN REUSED · provider was not called."
                    )
            else:
                from memcommit.study_prewarm.update import (
                    find_installed_projectable_update_prewarm,
                )

                update_prewarm_match = find_installed_projectable_update_prewarm(
                    store=store,
                    source=source,
                    target=target,
                    source_include_descendants=source_descendants,
                    target_include_descendants=target_descendants,
                    granted_source=granted_source,
                    granted_target=granted_target,
                )
                if update_prewarm_match is not None:
                    session = update_prewarm_match.session.with_status("staged")
                    update_analysis_origin = update_prewarm_match.origin
                    label = (
                        "EXACT PREWARM"
                        if update_prewarm_match.origin == "EXACT_PREWARM"
                        else "EQUIVALENT SCOPE PREWARM"
                        if update_prewarm_match.origin
                        == "EQUIVALENT_SCOPE_PREWARM"
                        else "PROJECTED PREWARM"
                    )
                    typer.echo(
                        f"{label} · UPDATE PLAN REUSED · provider was not called."
                    )
                else:
                    session = _plan_update_with_wait(
                        source,
                        target,
                        source_descendants=source_descendants,
                        target_descendants=target_descendants,
                        granted_source=granted_source,
                        granted_target=granted_target,
                    )
            # Bind the staged intent to the active record observed above.
            # This prevents two update processes from silently replacing one
            # another between planning and local application.
            store.save_staged_update(
                session,
                expected_current=existing,
            )
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
        if _interactive_terminal():

            def incorporate_comments(
                current: UpdateSession,
                guidance: str,
            ) -> UpdateSession:
                revised = _revise_update_with_wait(
                    current,
                    source,
                    target,
                    guidance,
                )
                # The comment turn replaces only the exact staged proposal it
                # reviewed. A concurrent Update must never be overwritten.
                store.save_staged_update(revised, expected_current=current)
                return revised

            if update_analysis_origin is None:
                reviewed = review_update_application(
                    session,
                    incorporate=incorporate_comments,
                )
            else:
                reviewed = review_update_application(
                    session,
                    incorporate=incorporate_comments,
                    analysis_origin=update_analysis_origin,
                )
            if reviewed is None:
                current = store.load_staged_update() or session
                render_plan(current, staged=True)
                typer.echo("Update remains staged; no target changes were applied.")
                return
            session = reviewed
        if session.granted_target is not None:
            applied = apply_granted_staged_update(store, session)
        elif session.granted_source is not None:
            applied = apply_granted_source_staged_update(store, session)
        else:
            applied = store.apply_staged_update(session)
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
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_plan(applied, applied=True)
