"""Create, review, and materialize one Source × Criteria Sever session."""

from __future__ import annotations

import sys
from typing import Annotated, Literal, Optional

import typer

from memcommit.application.capabilities.review_policy import (
    ownership_aware_application_review,
)
from memcommit.application.capabilities.authority.access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    choose_session,
)
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.adapters.console.coordination.context_operand import ContextOperandSnapshot
from memcommit.adapters.console.commands.sever.sessions import (
    list_sever_session_catalog,
    reload_selected_sever_session,
)
from memcommit.core.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.core.context_targeting.operands import choose_endpoint_operand
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.adapters.console.terminal.components.context_picker import context_memory_rows
from memcommit.adapters.console.commands.sever.setup import (
    choose_sever_setup,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.core.context_targeting.presets import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.application.capabilities.resolution.workbench import ResolutionNavigation
from memcommit.application.operations.sever.model import (
    SeverError,
    SeverSelection,
    SeverSession,
)
from memcommit.adapters.console.coordination.command_review import (
    sever as sever_command_review,
)
from memcommit.application.operations.sever.application import (
    SeverAnalysisProgress,
    SeverAnalysisRequest,
    SeverAnalysisResult,
    SeverApplicationError,
    SeverApplyRequest,
    SeverDecisionRequest,
    SeverDestinationRequest,
    SeverPersistedApplyRequest,
    SeverSessionSnapshot,
)
from memcommit.application.operations.sever.provider import SeverProviderError
from memcommit.application.operations.sever.resolution_adapter import (
    SeverResolutionWorkbenchAdapter,
    sever_memory_changes,
)
from memcommit.application.operations.sever.runtime import (
    capture_sever_binding,
    execute_sever_analysis,
    execute_sever_apply,
    execute_sever_session_apply,
    execute_sever_session_decision,
    execute_sever_session_destination_change,
    execute_sever_session_open,
    execute_sever_session_start,
)
from memcommit.application.operations.sever.session_store import SeverSessionStore
from memcommit.persistence.store import MemoryStore


# Compatibility name for callers that historically caught the command-local
# error. New non-terminal code owns the error at the application boundary.
SeverCommandError = SeverApplicationError


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


_capture_binding = capture_sever_binding


def _start_progress(progress, event: SeverAnalysisProgress) -> None:
    """Project typed application stages into the existing command wait view."""

    if event.stage == "PREPARED_REUSED":
        progress.update("reusing prepared analysis", step=3)
    elif event.stage == "CONNECTING_PROVIDER":
        progress.update("connecting provider", step=2)
    elif event.stage == "ANALYZING":
        progress.update(
            f"analyzing {event.source_count} source x "
            f"{event.criteria_count} criteria",
            step=3,
        )


def _start_analysis(
    *,
    store: MemoryStore,
    current_name: str | None,
    source_name: str,
    criteria_name: str,
    output_name: str,
    source_descendants: bool = True,
    criteria_descendants: bool = True,
    provider_factory=None,
) -> SeverAnalysisResult:
    source_access = resolve_context_access(
        store,
        source_name,
        current_name=current_name,
        required_permission="READ",
    )
    criteria_access = resolve_context_access(
        store,
        criteria_name,
        current_name=current_name,
        required_permission="READ",
    )
    # Freeze relative locators into canonical public names before confirmation.
    # The application repeats authority checks before cache lookup or provider
    # construction, so this display preparation cannot authorize execution.
    request = SeverAnalysisRequest(
        source_locator=source_access.display_name,
        criteria_locator=criteria_access.display_name,
        output_name=output_name,
        source_include_descendants=source_descendants,
        criteria_include_descendants=criteria_descendants,
    )
    def freeze_and_analyze(progress) -> SeverAnalysisResult:
        return execute_sever_analysis(
            request,
            store=store,
            provider_factory=provider_factory or connect_codex_chatgpt_provider,
            progress_callback=lambda event: _start_progress(progress, event),
        )

    result = run_command_wait(
        "SEVER",
        "preparing source and criteria",
        total=3,
        work=freeze_and_analyze,
    )
    return result


def _start(
    *,
    store: MemoryStore,
    source_name: str,
    criteria_name: str,
    output_name: str,
    source_descendants: bool = True,
    criteria_descendants: bool = True,
    provider_factory=None,
) -> SeverSession:
    """Compatibility facade for historical command-level test callers."""

    snapshot = ContextOperandSnapshot.capture(store)
    return _start_analysis(
        store=store,
        current_name=snapshot.current_name,
        source_name=snapshot.resolve(source_name),
        criteria_name=snapshot.resolve(criteria_name),
        output_name=output_name,
        source_descendants=source_descendants,
        criteria_descendants=criteria_descendants,
        provider_factory=provider_factory,
    ).session


def render_sever(session: SeverSession) -> str:
    self_save = session.save_mode == "SELF_SAVE"
    lines = [
        f"SEVER · {session.state} · "
        + ("SELF-SAVE" if self_save else "OTHER-SAVE"),
        f"SOURCE · {safe_terminal_text(session.source.root_name)} · "
        f"{'INCLUDE DESCENDANTS' if session.source.include_descendants else 'THIS CONTEXT ONLY'} · "
        f"{len(session.source.memories)} Memories",
        f"CRITERIA · {safe_terminal_text(session.criteria.root_name)} · "
        f"{'INCLUDE DESCENDANTS' if session.criteria.include_descendants else 'THIS CONTEXT ONLY'}",
        f"OUTPUT · {safe_terminal_text(session.output_name)} · "
        + (
            "SOURCE UPDATED"
            if self_save and session.state == "APPLIED"
            else "WILL UPDATE SOURCE"
            if self_save
            else "CREATED LOCALLY"
            if session.state == "APPLIED"
            else "READY TO CREATE"
        ),
        "",
        safe_terminal_text(session.overview),
        "",
        "CANDIDATES",
    ]
    for index, candidate in enumerate(session.candidates, 1):
        source = session.source_memory(candidate.source_memory_uid)
        label = (
            candidate.selection
            if candidate.selection != "RECOMMENDED"
            else candidate.recommendation
        )
        result = (
            "(forgotten)"
            if candidate.selection == "FORGET"
            or (
                candidate.selection == "RECOMMENDED"
                and candidate.recommendation == "FORGET"
            )
            else candidate.custom_content
            if candidate.selection == "CUSTOM"
            else source.content
            if candidate.selection == "AS_WRITTEN"
            else candidate.proposed_content
        )
        lines.extend(
            [
                f"  {index}. [{candidate.uid[:8]}] {label}",
                f"     SOURCE · {safe_terminal_text(source.content)}",
                f"     RESULT · {safe_terminal_text(result)}",
                f"     WHY · {safe_terminal_text(candidate.rationale)}",
            ]
        )
    excluded_query_names = tuple(
        dict.fromkeys(
            (
                *session.source.excluded_query_context_names,
                *session.criteria.excluded_query_context_names,
            )
        )
    )
    if excluded_query_names:
        lines.extend(
            [
                "",
                "NOT INCLUDED · "
                + ", ".join(safe_terminal_text(name) for name in excluded_query_names),
                "These query-only Contexts do not grant readable Memory access.",
            ]
        )
    lines.extend(
        [
            "",
            (
                "The reviewed Result replaces the Source Context on Apply."
                if self_save
                else "Apply creates a separate Result Context."
            ),
        ]
    )
    if session.state == "APPLIED":
        lines.append("RECOVERY · mem undo")
    return "\n".join(lines)


def render_sever_receipt(session: SeverSession) -> str:
    """Render terminal Sever success without reopening candidate details."""

    if session.state != "APPLIED" or session.application is None:
        raise SeverCommandError("Sever receipt requires an applied session.")
    forgotten = sum(
        candidate.selection == "FORGET"
        or (
            candidate.selection == "RECOMMENDED"
            and candidate.recommendation == "FORGET"
        )
        for candidate in session.candidates
    )
    self_save = session.save_mode == "SELF_SAVE"
    lines = [
        f"SEVER APPLIED · {session.source.root_name} → {session.output_name}",
        f"SAVE MODE · {'SELF-SAVE' if self_save else 'OTHER-SAVE'}",
        f"DECISIONS · KEEP {len(session.application.result_memory_uids)} · FORGET {forgotten}",
        "SOURCE · UPDATED" if self_save else "RESULT · CREATED SEPARATELY",
        f"RECEIPT · {session.uid}",
        f"CHECKPOINT · {session.application.checkpoint_uid}",
        f"REVIEW · mem review sever --session {session.uid}",
        "RECOVERY · mem undo",
    ]
    return "\n".join(lines)


def render_sever_incomplete_receipt(session: SeverSession) -> str:
    """Return saved Sever state without repeating its candidate report."""

    view = SeverResolutionWorkbenchAdapter(session).view()
    required = sum(
        item.effective_obligation == "REQUIRED"
        and item.response_state != "ANSWERED"
        for item in view.items
    )
    output_state = (
        "WILL UPDATE SOURCE"
        if session.save_mode == "SELF_SAVE"
        else "READY TO CREATE"
    )
    return "\n".join(
        [
            f"SEVER {'NEEDS INPUT' if required else 'READY'} · "
            f"{session.source.root_name} → {session.output_name}",
            f"JUDGMENTS · REQUIRED {required}",
            f"OUTPUT · {session.output_name} · {output_state}",
            f"SESSION · {session.uid}",
            "SOURCE · UNCHANGED",
            f"IMPACT · mem impact sever --session {session.uid}",
            f"RESUME · mem sever --resume {session.uid}",
        ]
    )


def _apply(store: MemoryStore, session: SeverSession) -> SeverSession:
    return execute_sever_apply(
        SeverApplyRequest(session=session),
        store=store,
    ).session


def _interactive_setup(store: MemoryStore) -> tuple[str, str, str, bool, bool] | None:
    names = tuple(store.list_context_names())
    granted = freeze_granted_context_navigation(store)
    current_name = store.current_context_name()

    def load_setup_memories(context_name: str):
        if context_name in names:
            return context_memory_rows(store.load(context_name))
        access = resolve_context_access(
            store,
            context_name,
            current_name=current_name,
            required_permission="READ",
        )
        return context_memory_rows(
            GrantedReadStore(access).load(access.display_name)
        )

    receipt = choose_sever_setup(
        names,
        current=current_name,
        virtual_names=granted.names,
        selectable_virtual_names=granted.selectable_names,
        annotations=granted.annotations,
        memory_loader=load_setup_memories,
    )
    if receipt is None:
        return None
    return (
        receipt.source_name,
        receipt.criteria_name,
        receipt.output_name,
        receipt.source_descendants,
        receipt.criteria_descendants,
    )


def _render_saved_session_list(sessions: SeverSessionStore) -> None:
    """Keep the existing non-TTY listing stable and provider-free."""

    saved = sessions.list()
    if not saved:
        typer.echo("No saved Sever sessions.")
        return
    for item in saved:
        typer.echo(
            f"{item.uid} · {item.state} · {item.source.root_name} × "
            f"{item.criteria.root_name} → {item.output_name}"
        )


def _choose_saved_sever_session(
    sessions: SeverSessionStore,
) -> tuple[Literal["OPEN", "NEW", "CANCEL"], SeverSession | None]:
    """Return OPEN, NEW, or CANCEL from the shared saved-work launcher."""

    catalog = list_sever_session_catalog(sessions)
    by_key = {entry.picker_entry.key: entry for entry in catalog}
    receipt = choose_session(
        tuple(entry.picker_entry for entry in catalog),
        title="MEM SEVER · SAVED SESSIONS",
        new_receipt=SessionNewReceipt(kind="sever", argv=("mem", "sever")),
    )
    if receipt is None:
        return "CANCEL", None
    if isinstance(receipt, SessionNewReceipt):
        if receipt.kind != "sever" or receipt.argv != ("mem", "sever"):
            raise SeverCommandError(
                "Sever session picker returned an invalid new-session receipt."
            )
        return "NEW", None
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != "sever":
        raise SeverCommandError("Sever session picker returned an invalid receipt.")
    entry = by_key.get(receipt.key)
    if entry is None or receipt.argv != entry.picker_entry.reopen_argv:
        raise SeverCommandError("Sever session picker returned a stale receipt.")
    return "OPEN", reload_selected_sever_session(sessions, entry)


def _run_workbench(
    store: MemoryStore,
    session: SeverSession,
    *,
    allow_apply: bool = True,
) -> SeverSession:
    from memcommit.adapters.console.terminal.components.resolution.session_shell import (
        ResolutionDestination,
        run_resolution_workbench_shell,
    )
    from memcommit.adapters.console.terminal.components.impact import ImpactController
    from memcommit.adapters.console.commands.sever.review import sever_review_report

    snapshot = execute_sever_session_open(session.uid, store=store)
    if snapshot.session != session:
        raise SeverCommandError(
            "The Sever session changed before its workbench opened. Reopen it."
        )
    navigation = ResolutionNavigation()
    while snapshot.session.state == "REVIEWING":
        session = snapshot.session

        def validate_destination(name: str) -> None:
            validate_portable_context_name(name)
            if name == session.source.root_name:
                if (
                    session.source.granted is not None
                    or session.source.include_descendants
                ):
                    raise ValueError(
                        "Self-save requires an ordinary local Source root with "
                        "Source descendants excluded."
                    )
                return
            if name != session.output_name and store.context_exists(name):
                raise ValueError(f"Output Context '{name}' already exists.")

        adapter = SeverResolutionWorkbenchAdapter(session)
        review_view = None
        if not allow_apply:
            review_view = sever_review_report(session).report().view
            if review_view is None:
                raise SeverCommandError("Sever Review report has no interactive view.")
        active_view = review_view if review_view is not None else adapter.view()
        impact_controller = ImpactController.from_memory_changes(
            operation=active_view.operation,
            artifact_uid=active_view.artifact_uid,
            revision=active_view.revision,
            title=(
                "IMPACT · SEVER SELF-SAVE · SOURCE WILL BE REPLACED"
                if session.save_mode == "SELF_SAVE"
                else "IMPACT · SEVER OTHER-SAVE"
            ),
            summary=(
                "This is the exact local result that Apply would save. "
                + (
                    "It replaces the Source Context."
                    if session.save_mode == "SELF_SAVE"
                    else "It creates a separate Result Context."
                )
            ),
            changes=sever_memory_changes(session),
        )
        action = run_resolution_workbench_shell(
            active_view,
            navigation=navigation,
            terminal_label="Interactive Sever",
            snapshot_hint="Run 'mem sever --resume SESSION' outside a TTY for a snapshot.",
            review_and_apply=allow_apply,
            decision_free_behavior=(
                ownership_aware_application_review(
                    mutates_granted_authority=False,
                    local_undo_available=True,
                ).decision_free_behavior
                if allow_apply
                else "REPORT_FIRST"
            ),
            split_viewer_items=True,
            impact_controller=None if not allow_apply else impact_controller,
            destination=(
                ResolutionDestination(
                    value=session.output_name,
                    state="CREATE ON APPLY",
                    validate=validate_destination,
                    context_names=tuple(store.list_context_names()),
                    current_context=store.current_context_name(),
                )
                if allow_apply
                else None
            ),
            turn_command_review=lambda proposed: (
                sever_command_review.build_turn_review(
                    session_uid=session.uid,
                    candidate_uid=proposed.item_uid,
                    choice=(
                        "custom"
                        if proposed.comment.strip()
                        else (proposed.option_uid or "").rpartition(":")[2]
                    ),
                    comment=proposed.comment.strip(),
                    expected_session=snapshot.version_token,
                )
                if proposed.kind == "SUBMIT_ITEM"
                and proposed.item_uid is not None
                else None
            ),
            compact_decisions=allow_apply,
        )
        if action.kind == "CLOSE":
            break
        if action.kind == "CHANGE_DESTINATION":
            if not allow_apply or action.destination is None:
                raise SeverCommandError("Review cannot change a Sever output location.")
            validate_destination(action.destination)
            snapshot = execute_sever_session_destination_change(
                SeverDestinationRequest(
                    snapshot=snapshot,
                    output_name=action.destination,
                ),
                store=store,
            )
            continue
        if action.kind == "ACCEPT":
            if not allow_apply:
                raise SeverCommandError("Review cannot apply a Sever output.")
            snapshot = execute_sever_session_apply(
                SeverPersistedApplyRequest(snapshot=snapshot),
                store=store,
            ).snapshot
            break
        if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
            raise SeverCommandError("Unsupported Sever workbench action.")
        selection: SeverSelection
        if action.comment.strip():
            selection = "CUSTOM"
            custom_content = action.comment.strip()
        else:
            suffix = (action.option_uid or "").rpartition(":")[2]
            selection = {
                "recommended": "RECOMMENDED",
                "as-written": "AS_WRITTEN",
                "forget": "FORGET",
            }.get(suffix)  # type: ignore[assignment]
            if selection is None:
                raise SeverCommandError("Unsupported Sever decision.")
            custom_content = ""
        snapshot = execute_sever_session_decision(
            SeverDecisionRequest(
                snapshot=snapshot,
                candidate_uid=action.item_uid,
                selection=selection,
                custom_content=custom_content,
            ),
            store=store,
        )
    return snapshot.session


def run_sever_review(store: MemoryStore, session: SeverSession) -> SeverSession:
    """Run Sever decisions without exposing output materialization."""
    return _run_workbench(store, session, allow_apply=False)


def _resolve_endpoint_syntax(
    endpoints: list[str] | None,
    *,
    source_name: str | None,
    criteria_name: str | None,
    save_as: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Normalize positional roles and their compatibility options."""

    positional = tuple(endpoints or ())
    if len(positional) > 3:
        raise SeverCommandError(
            "expected at most three positional Contexts: SOURCE CRITERIA [RESULT]."
        )
    resolved = [source_name, criteria_name, save_as]
    role_options = (
        "--source/--from",
        "--criteria/--against",
        "--save-as/--to",
    )
    role_names = ("SOURCE", "CRITERIA", "RESULT")
    for index, value in enumerate(positional):
        if resolved[index] is not None:
            raise SeverCommandError(
                f"{role_names[index]} was supplied both positionally and with "
                f"{role_options[index]}."
            )
        resolved[index] = value
    return resolved[0], resolved[1], resolved[2]


def cmd(
    contexts: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                "SOURCE and CRITERIA Contexts, plus an optional RESULT; "
                "omit RESULT to self-save or name a new Context to save elsewhere"
            ),
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--source",
            help="Compatibility alias for the existing Source Context",
        ),
    ] = None,
    from_: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Directional compatibility alias for --source",
        ),
    ] = None,
    criteria_name: Annotated[
        Optional[str],
        typer.Option(
            "--criteria",
            help="One readable Criteria root Context",
        ),
    ] = None,
    against: Annotated[
        Optional[str],
        typer.Option(
            "--against",
            help="Compatibility alias for --criteria",
        ),
    ] = None,
    save_as: Annotated[
        Optional[str],
        typer.Option(
            "--save-as",
            help=(
                "Save to SOURCE for self-save or to a fresh Context for other-save; "
                "omission self-saves"
            ),
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Directional compatibility alias for --save-as Result",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only the selected Source and Criteria roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both Source and Criteria roots",
        ),
    ] = False,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Include the Source root's readable descendant Contexts",
        ),
    ] = None,
    criteria_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--criteria-descendants/--criteria-root-only",
            legacy_root_only_option_alias("criteria"),
            help="Include the Criteria root's readable descendant Contexts",
        ),
    ] = None,
    resume: Annotated[
        Optional[str],
        typer.Option("--resume", help="Enter one exact saved Sever session by UID"),
    ] = None,
    candidate: Annotated[
        Optional[str],
        typer.Option(
            "--candidate", help="Candidate uid or unique prefix for a scripted decision"
        ),
    ] = None,
    choice: Annotated[
        Optional[str],
        typer.Option("--choice", help="recommended, as-written, forget, or custom"),
    ] = None,
    comment: Annotated[
        Optional[str],
        typer.Option(
            "--comment", help="Exact custom result content when --choice custom"
        ),
    ] = None,
    expect_session: Annotated[
        Optional[str],
        typer.Option(
            "--expect-session",
            metavar="SHA256",
            help="Require the exact saved Sever revision reviewed for this decision",
        ),
    ] = None,
    accept: Annotated[
        bool,
        typer.Option(
            "--accept",
            help="Apply the reviewed self-save or other-save Result",
        ),
    ] = False,
    sessions_flag: Annotated[
        bool,
        typer.Option("--sessions", help="Enter the interactive Sever session launcher"),
    ] = False,
) -> None:
    try:
        source_option = choose_endpoint_operand(
            None,
            role="SOURCE",
            options=(("--source", source_name), ("--from", from_)),
        )
        criteria_option = choose_endpoint_operand(
            None,
            role="CRITERIA",
            options=(("--criteria", criteria_name), ("--against", against)),
        )
        result_option = choose_endpoint_operand(
            None,
            role="RESULT",
            options=(("--save-as", save_as), ("--to", to)),
        )
        source_name, criteria_name, save_as = _resolve_endpoint_syntax(
            contexts,
            source_name=source_option,
            criteria_name=criteria_option,
            save_as=result_option,
        )
    except (SeverCommandError, ValueError) as error:
        typer.secho(
            f"Sever error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    scope_flags_supplied = (
        direct
        or recursive
        or source_descendants is not None
        or criteria_descendants is not None
    )
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        source_descendants, criteria_descendants = resolve_descendant_scopes(
            preset=preset,
            explicit=(source_descendants, criteria_descendants),
        )
    except (TypeError, ValueError) as error:
        typer.secho(
            f"Sever error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore()
    context_snapshot = ContextOperandSnapshot.capture(store)
    session_store = SeverSessionStore(store)
    try:
        if sessions_flag:
            if (
                any(
                    value is not None
                    for value in (
                        source_name,
                        criteria_name,
                        save_as,
                        resume,
                        candidate,
                        choice,
                        comment,
                        expect_session,
                    )
                )
                or accept
                or scope_flags_supplied
            ):
                raise SeverCommandError(
                    "--sessions cannot be combined with another Sever action."
                )

        interactive = _interactive_terminal()
        if (
            scope_flags_supplied
            and source_name is None
            and criteria_name is None
            and save_as is None
            and resume is None
        ):
            raise SeverCommandError(
                "Scope flags require an explicit --source/--criteria setup; "
                "interactive setup owns its visible ranges."
            )
        session: SeverSession | None = None
        snapshot: SeverSessionSnapshot | None = None
        sever_prewarm_origin: str | None = None
        start_new_from_sessions = False
        if sessions_flag:
            if not interactive:
                _render_saved_session_list(session_store)
                return
            launcher_action, selected_session = _choose_saved_sever_session(
                session_store
            )
            if launcher_action == "CANCEL":
                typer.echo("Sever selection cancelled. No session was opened.")
                return
            if launcher_action == "OPEN":
                if selected_session is None:
                    raise SeverCommandError(
                        "Sever session picker returned no selected session."
                    )
                snapshot = execute_sever_session_open(
                    selected_session.uid,
                    store=store,
                )
                if snapshot.session != selected_session:
                    raise SeverCommandError(
                        "The selected Sever session changed before it opened."
                    )
                session = snapshot.session
            elif launcher_action == "NEW":
                start_new_from_sessions = True
            else:
                raise SeverCommandError(
                    "Sever session picker returned an unsupported action."
                )

        if session is not None:
            pass
        elif resume is not None:
            if any(
                value is not None for value in (source_name, criteria_name, save_as)
            ):
                raise SeverCommandError(
                    "--resume cannot be combined with Source, Criteria, or output operands."
                )
            snapshot = execute_sever_session_open(resume, store=store)
            session = snapshot.session
        else:
            if (
                start_new_from_sessions
                or source_name is None
                and criteria_name is None
                and save_as is None
            ):
                if not interactive:
                    typer.echo(
                        "No Sever setup supplied. Use SOURCE CRITERIA [RESULT], or run in a TTY."
                    )
                    return
                setup = _interactive_setup(store)
                if setup is None:
                    typer.echo("Sever setup cancelled. No session created.")
                    return
                (
                    source_name,
                    criteria_name,
                    save_as,
                    source_descendants,
                    criteria_descendants,
                ) = setup
            if criteria_name is None:
                raise SeverCommandError("Starting Sever requires CRITERIA.")
            source_name = context_snapshot.resolve_or_current(source_name)
            if source_name is None:
                raise SeverCommandError(
                    "Starting Sever requires SOURCE or a current Context."
                )
            criteria_name = context_snapshot.resolve(criteria_name)
            if save_as is None:
                # SOURCE and CRITERIA were resolved against one command-start
                # snapshot. Reuse that frozen canonical Source name so omitted
                # RESULT cannot change meaning with later global-current state.
                save_as = source_name
            if source_descendants is None or criteria_descendants is None:
                raise SeverCommandError("Sever scope resolution produced no range.")
            analysis = _start_analysis(
                store=store,
                current_name=context_snapshot.current_name,
                source_name=source_name,
                criteria_name=criteria_name,
                output_name=save_as,
                source_descendants=source_descendants,
                criteria_descendants=criteria_descendants,
            )
            stored = execute_sever_session_start(analysis, store=store)
            snapshot = stored.snapshot
            session = snapshot.session
            sever_prewarm_origin = (
                stored.origin if stored.origin == "EXACT_PREWARM" else None
            )

        if session is None or snapshot is None:
            raise SeverCommandError("Sever session lifecycle produced no snapshot.")

        if candidate is not None or choice is not None or comment is not None:
            if candidate is None or choice is None:
                raise SeverCommandError(
                    "A scripted decision requires --candidate and --choice."
                )
            if (
                expect_session is not None
                and expect_session != snapshot.version_token
            ):
                raise SeverCommandError(
                    "The saved Sever session changed after this command was reviewed. "
                    "Reopen it and rebuild the decision command."
                )
            matches = [
                item for item in session.candidates if item.uid.startswith(candidate)
            ]
            if len(matches) != 1:
                raise SeverCommandError("Candidate selector is missing or ambiguous.")
            normalized = choice.lower()
            selections: dict[str, SeverSelection] = {
                "recommended": "RECOMMENDED",
                "as-written": "AS_WRITTEN",
                "forget": "FORGET",
                "custom": "CUSTOM",
            }
            if normalized not in selections:
                raise SeverCommandError(
                    "--choice must be recommended, as-written, forget, or custom."
                )
            if normalized == "custom" and (comment is None or not comment.strip()):
                raise SeverCommandError(
                    "--choice custom requires --comment with exact result content."
                )
            if normalized != "custom" and comment is not None:
                raise SeverCommandError("--comment is valid only with --choice custom.")
            snapshot = execute_sever_session_decision(
                SeverDecisionRequest(
                    snapshot=snapshot,
                    candidate_uid=matches[0].uid,
                    selection=selections[normalized],
                    custom_content=(comment or "").strip(),
                ),
                store=store,
            )
            session = snapshot.session

        elif expect_session is not None:
            raise SeverCommandError(
                "--expect-session requires a scripted --candidate and --choice decision."
            )

        if accept:
            applied = execute_sever_session_apply(
                SeverPersistedApplyRequest(snapshot=snapshot),
                store=store,
            )
            snapshot = applied.snapshot
            session = snapshot.session
        elif sys.stdin.isatty() and sys.stdout.isatty():
            session = _run_workbench(store, session)

        if sever_prewarm_origin:
            typer.echo("ANALYSIS · EXACT PREWARM · PROVIDER NOT CALLED")
        if session.state == "APPLIED":
            typer.echo(render_sever_receipt(session))
        else:
            typer.echo(render_sever_incomplete_receipt(session))
    except (
        FileNotFoundError,
        OSError,
        QueryProviderError,
        SeverCommandError,
        SeverError,
        SeverProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Sever error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
