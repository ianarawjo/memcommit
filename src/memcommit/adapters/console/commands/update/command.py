"""Apply or reopen a semantic update from Context A to a local target B."""

from datetime import datetime
import sys
from typing import Annotated, Optional

import typer

from memcommit.application.flow import run_application_flow
from memcommit.adapters.console.commands.shared.command_wait import (
    CommandWaitView,
    run_command_wait,
)
from memcommit.adapters.console.commands.update.setup import choose_update_setup
from memcommit.application.authority.access import (
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
)
from memcommit.adapters.interfaces.tui.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.adapters.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.commands.update.render import (
    render_plan,
    render_update_receipt,
    render_update_report_snapshot,
    review_update_application,
)
from memcommit.core.context import Context
from memcommit.application.context_locator import resolve_context_locator
from memcommit.core.context_targeting.loading import load_context_scope
from memcommit.core.context_targeting.model import InlineTextOperand
from memcommit.core.context_targeting.operands import (
    classify_context_or_inline_text_operand,
)
from memcommit.application.semantic.goal_focus import FrozenGoalFocus
from memcommit.application.semantic.goal_focus_runtime import (
    freeze_goal_focus_operand,
    revalidate_goal_focus,
)
from memcommit.core.context_targeting.presets import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.application.authority.derived_policy import authorize_derived_transfer
from memcommit.application.operations.update.granted_source_application import (
    apply_granted_source_staged_update,
)
from memcommit.application.operations.update.granted_application import (
    apply_granted_staged_update,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.persistence.store import MemoryStore
from memcommit.study_scenarios.legacy.prewarm.registry import StudyPrewarmRegistryError
from memcommit.application.operations.update.model import (
    GrantedUpdateTarget,
    UpdateError,
    UpdateSession,
    applied_session_matches,
    collect_update_inputs,
    inline_update_context,
    plan_update,
    revise_update,
    session_matches,
    update_session_record_digest,
)
from memcommit.application.operations.update.application_flow import (
    UpdateApplicationFlowPort,
)
from memcommit.application.operations.update.endpoints import (
    choose_update_endpoint_operands,
    resolve_update_endpoints,
)


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _run_saved_update_workbench(session: UpdateSession) -> bool:
    """Open the shared state-aware Update surface without eager UI imports."""

    from memcommit.adapters.console.commands.impact.sessions import (
        run_impact_session_workbench,
        update_impact_presentation,
    )

    return run_impact_session_workbench(
        update_impact_presentation(session),
        terminal_label="Interactive saved Update Impact",
    )


def _start_new_update_from_setup(store: MemoryStore) -> None:
    """Collect one new Update request without browsing saved sessions."""

    setup = choose_update_setup(store)
    if setup is None:
        typer.echo("Update setup cancelled; no session was created.")
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
    # The reviewed setup supplies explicit endpoints before returning to the
    # ordinary command boundary; a prior singleton session cannot redirect it.
    cmd(**start_kwargs)


def _browse_saved_update(store: MemoryStore) -> None:
    """Browse the singleton receipt; New delegates to the shared setup."""
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
                reopen_argv=("mem", "update", "--sessions"),
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
        _start_new_update_from_setup(store)
        return
    if (
        not isinstance(receipt, SessionOpenReceipt)
        or receipt.kind != "update"
        or session is None
        or receipt.key != session.uid
        or receipt.argv != ("mem", "update", "--sessions")
    ):
        raise UpdateError("Update session picker returned an invalid receipt.")
    current = store.load_staged_update()
    if current is None or current.to_dict() != session.to_dict():
        raise UpdateError(
            "The saved Update session changed while the launcher was open. Reopen it."
        )
    if current.status == "applied":
        typer.echo(render_update_receipt(current))
        return
    if current.status == "undone":
        typer.echo(
            f"UPDATE UNDONE · {current.source_name} → {current.target_name}\n"
            f"SESSION · {current.uid}\n"
            "RECOVERY · mem redo"
        )
        return
    if current.status == "impact":
        typer.echo(
            f"UPDATE IMPACT SAVED · {current.source_name} → {current.target_name}\n"
            f"SESSION · {current.uid}\n"
            f"IMPACT · mem impact update --session {current.uid}"
        )
        return

    # Re-enter execution directly. Only outstanding judgments are shown; the
    # retained report remains behind the explicit Impact command.
    resume_kwargs = {
        "target_name": current.target_name,
        "replace_stage": False,
        "source_descendants": current.source_include_descendants,
        "target_descendants": current.target_include_descendants,
    }
    if current.inline_source_content is None:
        resume_kwargs["source_name"] = current.source_name
    else:
        resume_kwargs["memory"] = current.inline_source_content
    cmd(**resume_kwargs)


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
        "MEM UPDATE · INPUTS CONFIRMED · BUILDING PLAN",
        "",
        f"SOURCE A · {display_escape_text(source.name)}",
        "  SCOPE · "
        + ("INCLUDE DESCENDANTS" if source_descendants else "SELECTED GRAPH ONLY"),
        "  ROLE · INPUT TO THIS PLAN",
        "",
        f"TARGET B · {display_escape_text(target.name)}",
        "  SCOPE · "
        + ("INCLUDE DESCENDANTS" if target_descendants else "SELECTED GRAPH ONLY"),
        "  ROLE · CHANGES APPLY HERE AFTER REVIEW",
    ]
    if guidance is not None:
        lines.extend(
            [
                "",
                "REVISION COMMENT · SUBMITTED",
                safe_terminal_text(guidance),
            ]
        )
    lines.extend(
        [
            "",
            "Building the plan. Apply remains a separate review action.",
        ]
    )
    return CommandWaitView(
        title="UPDATE INPUTS",
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
            "PENDING REVISION · SUBMITTED",
            safe_terminal_text(guidance),
        ]
    )
    return CommandWaitView(
        title="PREVIOUS UPDATE REPORT",
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
    inline_source_content: str | None = None,
    goal_focus: FrozenGoalFocus | None = None,
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
            inline_source_content=inline_source_content,
            goal_focus=goal_focus,
        )

    return run_command_wait(
        "UPDATE",
        "connecting provider",
        total=2,
        work=plan,
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


def _review_granted_target_authority(
    prepared: UpdateSession,
    *,
    analysis_origin: str | None,
) -> UpdateSession | None:
    """Approve or close one exact external-owner plan without revising it."""

    if not _interactive_terminal():
        return prepared

    def reject_revision(
        _current: UpdateSession,
        _guidance: str,
    ) -> UpdateSession:
        raise RuntimeError("Granted Target approval cannot revise the Update plan.")

    return review_update_application(
        prepared,
        incorporate=reject_revision,
        analysis_origin=analysis_origin,
        allow_revision=False,
    )


def cmd(
    contexts: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="SOURCE [TARGET]",
            help=(
                "Source and optional Target Context; an unambiguous sentence "
                "is one process-local Source Memory"
            ),
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=(
                "Source Context A or unambiguous inline Memory; if --to is "
                "omitted, current supplies B"
            ),
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=("Target Context B; if --from is omitted, current supplies A"),
        ),
    ] = None,
    memory: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            help=(
                "Use exact text as one process-local Source Memory; current or "
                "--to supplies the Target"
            ),
        ),
    ] = None,
    goal: Annotated[
        Optional[str],
        typer.Option(
            "--goal",
            help=(
                "Optional relevance focus as a Context, CONTEXT:UID/UID "
                "Memory, or inline text; never treated as Update evidence"
            ),
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
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Enter the interactive Update session launcher",
        ),
    ] = False,
) -> None:
    positional_contexts = tuple(contexts or ())
    try:
        source_name, target_name = choose_update_endpoint_operands(
            positional_contexts,
            source_option=source_name,
            target_option=target_name,
            allow_single_source=True,
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
    if memory is not None and source_name is not None:
        typer.secho(
            "Update error: --memory supplies Source content and cannot be "
            "combined with positional Source or --from.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if sessions and (
        source_name is not None
        or target_name is not None
        or memory is not None
        or goal is not None
        or replace_stage
        or source_memory is not None
        or target_memory is not None
        or scope_flags_supplied
        or comment is not None
        or expect_session is not None
    ):
        typer.secho(
            "Update error: --sessions cannot be combined with Context operands "
            "or Update actions.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if sessions:
        store = MemoryStore(create=False)
        try:
            _browse_saved_update(store)
        except (OSError, UpdateError, ValueError) as error:
            typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        return
    if source_name is None and target_name is None and memory is None:
        if (
            source_memory is not None
            or target_memory is not None
            or scope_flags_supplied
            or comment is not None
            or expect_session is not None
            or goal is not None
        ):
            typer.secho(
                "Update error: scope or Goal options require --from or --to.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        store = MemoryStore(create=False)
        try:
            _start_new_update_from_setup(store)
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
    if memory is not None and (source_memory is not None or source_descendants):
        typer.secho(
            "Update error: inline --memory cannot use Source Memory focus or "
            "Source descendants.",
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
        requested_goal_focus = (
            freeze_goal_focus_operand(
                store,
                goal,
                current_name=current_name,
            )
            if goal is not None
            else None
        )
        if requested_goal_focus is not None:
            revalidate_goal_focus(store, requested_goal_focus)
        if target_name is not None:
            parsed_target = classify_context_or_inline_text_operand(
                target_name,
                current=current_name,
                context_exists=store.context_exists,
            )
            if isinstance(parsed_target, InlineTextOperand):
                if len(positional_contexts) == 2:
                    raise UpdateError(
                        "Positional Update operands are SOURCE TARGET; the "
                        "second operand is the Target. Inline text is supported "
                        "only as Source. To update the first Context from text, "
                        "use 'mem update --memory TEXT --to CONTEXT'."
                    )
                raise UpdateError(
                    "The Update Target must be an existing Context; inline text "
                    "is supported only as Source."
                )
            target_name = parsed_target.locator
        inline_source_content = memory
        if inline_source_content is None and source_name is not None:
            parsed_source = classify_context_or_inline_text_operand(
                source_name,
                current=current_name,
                context_exists=store.context_exists,
            )
            if isinstance(parsed_source, InlineTextOperand):
                inline_source_content = parsed_source.text
                source_name = None
            else:
                source_name = parsed_source.locator
        source_access = None
        if inline_source_content is not None:
            if source_descendants or source_memory is not None:
                raise UpdateError(
                    "Inline Update input cannot use Source descendants or "
                    "Source Memory focus."
                )
            if target_name is None:
                if not current_name:
                    raise UpdateError(
                        "Inline Update input uses the current Context as Target, "
                        "but no current Context is available. Supply --to TARGET."
                    )
                resolved_target_name = current_name
            else:
                resolved_target_name = resolve_context_locator(
                    target_name,
                    current=current_name,
                )
            source = inline_update_context(inline_source_content)
        else:
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
            resolved_target_name = endpoints.target_name
            source_store = (
                GrantedReadStore(source_access) if source_access.is_granted else store
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
        target_access = _resolve_update_access(
            store,
            resolved_target_name,
            current_name=current_name,
        )
        if inline_source_content is not None and target_access.is_granted:
            raise UpdateError(
                "Inline-Memory Update currently requires a local Target Context."
            )
        target_store = (
            GrantedReadStore(target_access) if target_access.is_granted else store
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
            if source_access is not None and source_access.is_granted
            else None
        )
        granted_target = (
            freeze_granted_context_binding(target_access)
            if target_access.is_granted
            else None
        )
        if source_access is not None:
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

    goal_focus = (
        requested_goal_focus
        if goal is not None
        else (
            existing.goal_focus if existing is not None and not replace_stage else None
        )
    )
    completed_previous: UpdateSession | None = None
    if existing is not None and existing.status == "applied":
        if (
            existing.source_include_descendants == source_descendants
            and existing.target_include_descendants == target_descendants
            and existing.source_memory_uid == requested_inputs.source_memory_uid
            and existing.target_memory_uid == requested_inputs.target_memory_uid
            and existing.goal_focus == goal_focus
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
            # A terminal receipt is evidence, not an unfinished work slot. Keep
            # it addressable by UID while the distinct invocation starts fresh.
            completed_previous = existing
            if goal is None:
                goal_focus = None

    try:
        if goal_focus is not None:
            revalidate_goal_focus(store, goal_focus)
    except (RuntimeError, ValueError) as error:
        typer.secho(f"Update error: {error}", fg=typer.colors.RED, err=True)
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
            and existing.goal_focus == goal_focus
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
            from memcommit.study_scenarios.legacy.prewarm.update import (
                installed_update_prewarm_origin,
            )

            update_analysis_origin = (
                None
                if inline_source_content is not None
                else installed_update_prewarm_origin(
                    store,
                    session,
                )
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
            typer.echo(
                "Update revision saved; review it before applying the target changes."
            )
            return
        if session is None:
            if (
                cached is not None
                and cached.source_include_descendants == source_descendants
                and cached.target_include_descendants == target_descendants
                and cached.source_memory_uid == requested_inputs.source_memory_uid
                and cached.target_memory_uid == requested_inputs.target_memory_uid
                and cached.goal_focus == goal_focus
                and session_matches(
                    cached,
                    source,
                    target,
                    granted_source=granted_source,
                    granted_target=granted_target,
                )
            ):
                session = cached.with_status("staged")
                from memcommit.study_scenarios.legacy.prewarm.update import (
                    installed_update_prewarm_origin,
                )

                origin = (
                    None
                    if inline_source_content is not None
                    else installed_update_prewarm_origin(store, cached)
                )
                if origin is not None:
                    update_analysis_origin = origin
                    label = (
                        "EXACT PREWARM"
                        if origin == "EXACT_PREWARM"
                        else (
                            "PROJECTED PREWARM"
                            if origin == "PROJECTED_PREWARM"
                            else "EQUIVALENT SCOPE PREWARM"
                        )
                    )
                    typer.echo(
                        f"{label} · UPDATE PLAN REUSED · provider was not called."
                    )
            else:
                from memcommit.study_scenarios.legacy.prewarm.update import (
                    find_installed_projectable_update_prewarm,
                )

                update_prewarm_match = (
                    None
                    if (
                        inline_source_content is not None
                        or goal_focus is not None
                        or source_memory is not None
                        or target_memory is not None
                    )
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
                        else (
                            "EQUIVALENT SCOPE PREWARM"
                            if update_prewarm_match.origin == "EQUIVALENT_SCOPE_PREWARM"
                            else "PROJECTED PREWARM"
                        )
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
                        inline_source_content=inline_source_content,
                        goal_focus=goal_focus,
                    )
            # Bind the staged intent to the active record observed above.
            # This prevents two update processes from silently replacing one
            # another between planning and local application.
            store.save_staged_update(
                session,
                expected_current=existing,
            )
            if completed_previous is not None:
                typer.echo(
                    "PREVIOUS UPDATE COMPLETE · "
                    f"{completed_previous.uid[:8]} · starting a new Update."
                )
                typer.echo(
                    "REVIEW PREVIOUS · mem review update --session "
                    f"{completed_previous.uid}"
                )
            if update_prewarm_match is not None:
                from memcommit.study_scenarios.legacy.prewarm.update import (
                    record_equivalent_update_prewarm,
                    record_exact_update_prewarm,
                    record_projected_update_prewarm,
                )

                recorder = (
                    record_exact_update_prewarm
                    if update_prewarm_match.origin == "EXACT_PREWARM"
                    else (
                        record_equivalent_update_prewarm
                        if update_prewarm_match.origin == "EQUIVALENT_SCOPE_PREWARM"
                        else record_projected_update_prewarm
                    )
                )
                recorder(
                    store,
                    entry_key=update_prewarm_match.entry_key,
                    session=session,
                    prepared_source_name=(update_prewarm_match.prepared_source_name),
                )

        if session.goal_focus is not None:
            revalidate_goal_focus(store, session.goal_focus)

        application = run_application_flow(
            session,
            port=UpdateApplicationFlowPort(
                local_applier=lambda reviewed: store.apply_staged_update(reviewed),
                granted_source_applier=lambda reviewed: (
                    apply_granted_source_staged_update(store, reviewed)
                ),
                granted_target_applier=lambda reviewed: (
                    apply_granted_staged_update(store, reviewed)
                ),
                authority_reviewer=lambda prepared: (
                    _review_granted_target_authority(
                        prepared,
                        analysis_origin=update_analysis_origin,
                    )
                ),
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
