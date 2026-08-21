"""Apply or reopen a semantic update from Context A to a local target B."""

from datetime import datetime
import sys
from typing import Annotated, Optional

import typer

from memcommit.application_flow import run_application_flow
from memcommit.commands.command_wait import (
    CommandWaitView,
    run_command_wait,
)
from memcommit.commands.update_setup import choose_update_setup
from memcommit.authority.access import (
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
)
from memcommit.interfaces.tui.components.operation_launcher.session import (
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
    render_update_receipt,
    render_update_report_snapshot,
    review_update_application,
)
from memcommit.context import Context
from memcommit.context_targeting.loading import load_context_scope
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
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
    collect_update_inputs,
    plan_update,
    revise_update,
    session_matches,
    update_session_record_digest,
)
from memcommit.update_application_flow import UpdateApplicationFlowPort
from memcommit.update_endpoints import (
    choose_update_endpoint_operands,
    resolve_update_endpoints,
)


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
        start_kwargs = {
            "source_name": setup.source_name,
            "target_name": setup.target_name,
            "source_descendants": setup.source_descendants,
            "target_descendants": setup.target_descendants,
        }
        if setup.source_memory_uid is not None:
            start_kwargs["source_memory"] = setup.source_memory_uid
        if setup.target_memory_uid is not None:
            start_kwargs["target_memory"] = setup.target_memory_uid
        cmd(**start_kwargs)
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
    source_memory_selector: str | None = None,
    target_memory_selector: str | None = None,
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
            source_memory_selector=source_memory_selector,
            target_memory_selector=target_memory_selector,
        )

    return run_command_wait(
        "UPDATE",
        "connecting provider",
        total=2,
        work=plan,
    )


def _review_update_for_application_flow(
    session: UpdateSession,
    incorporate,
    analysis_origin: str | None,
) -> UpdateSession | None:
    """Normalize the existing review API for the application flow adapter."""

    if analysis_origin is None:
        return review_update_application(session, incorporate=incorporate)
    return review_update_application(
        session,
        incorporate=incorporate,
        analysis_origin=analysis_origin,
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
    contexts: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="SOURCE TARGET",
            help="Explicit Source and Target Contexts",
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
    replace_stage: Annotated[
        bool,
        typer.Option(
            "--replace-stage",
            help="Replace a different, stale, or applied update record",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only the selected Source and Target roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both Source and Target roots",
        ),
    ] = False,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Include all readable descendant Contexts under Source A",
        ),
    ] = None,
    target_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--target-descendants/--target-root-only",
            legacy_root_only_option_alias("target"),
            help="Include all writable descendant Contexts under Target B",
        ),
    ] = None,
    source_memory: Annotated[
        Optional[str],
        typer.Option(
            "--source-memory",
            metavar="UID_OR_PREFIX",
            help=(
                "Use one Source Memory as provenance while its neighbors "
                "remain non-actionable context"
            ),
        ),
    ] = None,
    target_memory: Annotated[
        Optional[str],
        typer.Option(
            "--target-memory",
            metavar="UID_OR_PREFIX",
            help=(
                "Restrict edits/removal to one Target Memory while its "
                "neighbors remain non-actionable context"
            ),
        ),
    ] = None,
    comment: Annotated[
        Optional[str],
        typer.Option(
            "--comment",
            help="Rebuild the staged Update plan from one reviewed semantic turn",
        ),
    ] = None,
    expect_session: Annotated[
        Optional[str],
        typer.Option(
            "--expect-session",
            metavar="SHA256",
            help="Require the exact staged Update revision reviewed for this turn",
        ),
    ] = None,
) -> None:
    try:
        source_name, target_name = choose_update_endpoint_operands(
            contexts,
            source_option=source_name,
            target_option=target_name,
        )
    except ValueError as error:
        typer.secho(
            f"Update error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
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
        typer.secho(
            f"Update error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if (comment is None) != (expect_session is None):
        typer.secho(
            "Update error: --comment and --expect-session must be supplied together.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if comment is not None and not comment.strip():
        typer.secho(
            "Update error: --comment cannot be empty.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if comment is not None and replace_stage:
        typer.secho(
            "Update error: a semantic turn cannot replace the staged session boundary.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if source_name is None and target_name is None:
        if (
            source_memory is not None
            or target_memory is not None
            or scope_flags_supplied
            or comment is not None
            or expect_session is not None
        ):
            typer.secho(
                "Update error: scope flags require --from or --to.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        store = MemoryStore(create=False)
        try:
            _browse_saved_update(store)
        except (OSError, UpdateError, ValueError) as error:
            typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        return

    if source_memory is not None and source_descendants:
        typer.secho(
            "Update error: --source-memory cannot be combined with "
            "--source-descendants.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if target_memory is not None and target_descendants:
        typer.secho(
            "Update error: --target-memory cannot be combined with "
            "--target-descendants.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

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
            freeze_granted_context_binding(source_access)
            if source_access.is_granted
            else None
        )
        granted_target = (
            freeze_granted_context_binding(target_access)
            if target_access.is_granted
            else None
        )
        authorize_derived_transfer(source_access, target_access)
        requested_inputs = collect_update_inputs(
            source,
            target,
            source_memory_selector=source_memory,
            target_memory_selector=target_memory,
        )
    except (
        FileNotFoundError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        UpdateError,
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
            and existing.source_memory_uid == requested_inputs.source_memory_uid
            and existing.target_memory_uid == requested_inputs.target_memory_uid
            and applied_session_matches(
                existing,
                source,
                target,
                granted_source=granted_source,
                granted_target=granted_target,
            )
        ):
            typer.echo(render_update_receipt(existing))
            typer.echo("This Update receipt was already applied.")
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
            and existing.source_memory_uid == requested_inputs.source_memory_uid
            and existing.target_memory_uid == requested_inputs.target_memory_uid
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
        if comment is not None:
            if session is None or session.status != "staged":
                raise UpdateError(
                    "A semantic Update turn requires the matching staged session."
                )
            if update_session_record_digest(session) != expect_session:
                raise UpdateError(
                    "The staged Update session changed after this command was reviewed. "
                    "Reopen it and rebuild the turn command."
                )
            revised = _revise_update_with_wait(
                session,
                source,
                target,
                comment.strip(),
            )
            store.save_staged_update(revised, expected_current=session)
            render_plan(revised, staged=True)
            typer.echo("Update semantic turn saved; target changes were not applied.")
            return
        if session is None:
            if (
                cached is not None
                and cached.source_include_descendants == source_descendants
                and cached.target_include_descendants == target_descendants
                and cached.source_memory_uid == requested_inputs.source_memory_uid
                and cached.target_memory_uid == requested_inputs.target_memory_uid
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
                        source_memory_selector=source_memory,
                        target_memory_selector=target_memory,
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

        application = run_application_flow(
            session,
            port=UpdateApplicationFlowPort(
                interactive=_interactive_terminal(),
                decision_resolver=_review_update_for_application_flow,
                incorporate=incorporate_comments,
                local_applier=lambda reviewed: store.apply_staged_update(reviewed),
                granted_source_applier=lambda reviewed: (
                    apply_granted_source_staged_update(store, reviewed)
                ),
                granted_target_applier=lambda reviewed: (
                    apply_granted_staged_update(store, reviewed)
                ),
                analysis_origin=update_analysis_origin,
            ),
        )
        if application.status == "CANCELLED":
            current = store.load_staged_update() or session
            typer.echo(
                f"UPDATE INCOMPLETE · {current.source_name} → {current.target_name}"
            )
            typer.echo(f"SESSION · {current.uid}")
            typer.echo("No target changes were applied. Resume with mem update.")
            return
        applied = application.applied
        if applied is None:
            raise RuntimeError("Update application produced no durable receipt.")
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

    typer.echo(render_update_receipt(applied))
