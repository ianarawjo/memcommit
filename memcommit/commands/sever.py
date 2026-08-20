"""Create, review, and materialize one Source × Criteria Sever session."""

from __future__ import annotations

import sys
from typing import Annotated, Literal, Optional

import typer

from memcommit.application_review_policy import (
    ownership_aware_application_review,
)
from memcommit.authority.access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    choose_session,
)
from memcommit.commands.command_wait import (
    CommandWaitView,
    build_report_loading_view,
    run_command_wait,
)
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.sever_sessions import (
    list_sever_session_catalog,
    reload_selected_sever_session,
)
from memcommit.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.context_targeting.tui.picker import context_memory_rows
from memcommit.commands.sever_setup_shell import choose_sever_setup
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.sever import (
    SeverError,
    SeverSelection,
    SeverSession,
)
from memcommit.sever_application import (
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
from memcommit.sever_provider import SeverProviderError
from memcommit.sever_resolution_adapter import (
    SeverResolutionWorkbenchAdapter,
    sever_memory_changes,
)
from memcommit.sever_runtime import (
    capture_sever_binding,
    execute_sever_analysis,
    execute_sever_apply,
    execute_sever_session_apply,
    execute_sever_session_decision,
    execute_sever_session_destination_change,
    execute_sever_session_open,
    execute_sever_session_start,
)
from memcommit.sever_store import SeverSessionStore
from memcommit.store import MemoryStore, validate_context_name


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
    wait_view = CommandWaitView(
        title="SEVER CONFIRMED INPUTS · READ-ONLY",
        text="\n".join(
            [
                "MEM SEVER · FROZEN SETUP · RESULT PENDING",
                "",
                f"SOURCE · {safe_terminal_text(source_access.display_name)}",
                "  SCOPE · "
                + (
                    "INCLUDE DESCENDANTS"
                    if source_descendants
                    else "THIS CONTEXT ONLY"
                ),
                "  STATE · UNCHANGED",
                "",
                f"CRITERIA · {safe_terminal_text(criteria_access.display_name)}",
                "  SCOPE · "
                + (
                    "INCLUDE DESCENDANTS"
                    if criteria_descendants
                    else "THIS CONTEXT ONLY"
                ),
                "",
                f"OUTPUT · {safe_terminal_text(output_name)} · NOT CREATED",
                "",
                "The Sever review will replace this setup after analysis.",
            ]
        ),
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
        "freezing source and criteria",
        total=3,
        work=freeze_and_analyze,
        return_view=build_report_loading_view(
            "SEVER",
            sections=("What mem understood", "Candidates", "Output preview"),
        ),
        context_view=wait_view,
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
    lines = [
        f"SEVER · {session.state} · SOURCE UNCHANGED",
        f"SOURCE · {safe_terminal_text(session.source.root_name)} · "
        f"{'INCLUDE DESCENDANTS' if session.source.include_descendants else 'THIS CONTEXT ONLY'} · "
        f"{len(session.source.memories)} Memories",
        f"CRITERIA · {safe_terminal_text(session.criteria.root_name)} · "
        f"{'INCLUDE DESCENDANTS' if session.criteria.include_descendants else 'THIS CONTEXT ONLY'}",
        f"OUTPUT · {safe_terminal_text(session.output_name)} · "
        + ("CREATED LOCALLY" if session.state == "APPLIED" else "NOT CREATED"),
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
    lines.extend(["", "The Source Context is unchanged."])
    if session.state == "APPLIED":
        lines.append("RECOVERY · mem undo")
    return "\n".join(lines)


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
    from memcommit.commands.resolution_workbench_shell import (
        ResolutionDestination,
        run_resolution_workbench_shell,
    )
    from memcommit.impact_controller import ImpactController
    from memcommit.review_report_adapters import sever_review_report

    snapshot = execute_sever_session_open(session.uid, store=store)
    if snapshot.session != session:
        raise SeverCommandError(
            "The Sever session changed before its workbench opened. Reopen it."
        )
    navigation = ResolutionNavigation()
    while snapshot.session.state == "REVIEWING":
        session = snapshot.session

        def validate_destination(name: str) -> None:
            validate_context_name(name)
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
            title="IMPACT · LOCAL SEVER RESULT · SOURCE UNCHANGED",
            summary=(
                "This is the exact local result that Apply would materialize. "
                "The Source Context remains unchanged."
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
                    state="NOT CREATED",
                    validate=validate_destination,
                    context_names=tuple(store.list_context_names()),
                    current_context=store.current_context_name(),
                )
                if allow_apply
                else None
            ),
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


def cmd(
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--source",
            help="Existing ordinary Source Context; defaults to current only in explicit flag mode",
        ),
    ] = None,
    criteria_name: Annotated[
        Optional[str],
        typer.Option(
            "--criteria",
            "--against",
            help="One readable Criteria root Context; query-only views are rejected",
        ),
    ] = None,
    save_as: Annotated[
        Optional[str],
        typer.Option(
            "--save-as",
            help="New local Result Context name; never overwrites an existing Context",
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
    accept: Annotated[
        bool,
        typer.Option(
            "--accept",
            help="Create the reviewed local result Context; Source remains unchanged",
        ),
    ] = False,
    sessions_flag: Annotated[
        bool,
        typer.Option("--sessions", help="Enter the interactive Sever session launcher"),
    ] = False,
) -> None:
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
                    )
                )
                or accept
                or scope_flags_supplied
            ):
                raise SeverCommandError(
                    "--sessions cannot be combined with another Sever action."
                )

        interactive = _interactive_terminal()
        bare_launcher = (
            source_name is None
            and criteria_name is None
            and save_as is None
            and resume is None
            and candidate is None
            and choice is None
            and comment is None
            and not accept
            and not scope_flags_supplied
        )
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
        start_from_launcher = False
        if sessions_flag or bare_launcher:
            if not interactive:
                if sessions_flag:
                    _render_saved_session_list(session_store)
                else:
                    typer.echo(
                        "No Sever setup supplied. Use --source, --criteria, "
                        "and --save-as, or run in a TTY."
                    )
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
                start_from_launcher = True
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
                start_from_launcher
                or source_name is None
                and criteria_name is None
                and save_as is None
            ):
                if not interactive:
                    typer.echo(
                        "No Sever setup supplied. Use --source, --criteria, and --save-as, or run in a TTY."
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
            if criteria_name is None or save_as is None:
                raise SeverCommandError(
                    "Starting Sever requires --criteria and --save-as."
                )
            source_name = context_snapshot.resolve_or_current(source_name)
            if source_name is None:
                raise SeverCommandError(
                    "Starting Sever requires --source or a current Context."
                )
            criteria_name = context_snapshot.resolve(criteria_name)
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
        typer.echo(render_sever(session))
        typer.secho(f"Session · {session.uid}", fg=typer.colors.CYAN)
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
