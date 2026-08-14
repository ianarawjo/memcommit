"""Create, review, and materialize one Source × Criteria Sever session."""

from __future__ import annotations

import sys
from typing import Annotated, Literal, Optional

import typer

from memcommit.commands.granted_context import resolve_context_access
from memcommit.commands.session_picker import (
    SessionNewReceipt,
    SessionOpenReceipt,
    choose_session,
)
from memcommit.commands.command_wait import (
    CommandWaitView,
    build_report_loading_view,
    run_command_wait,
)
from memcommit.commands.sever_sessions import (
    list_sever_session_catalog,
    reload_selected_sever_session,
)
from memcommit.commands.switch import _granted_picker_state
from memcommit.commands.sever_setup_shell import choose_sever_setup
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
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
    sever_record_digest,
)
from memcommit.sever_application import (
    SeverAnalysisProgress,
    SeverAnalysisRequest,
    SeverAnalysisResult,
    SeverApplicationError,
    SeverApplyRequest,
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
    source_name: str,
    criteria_name: str,
    output_name: str,
    source_descendants: bool = True,
    criteria_descendants: bool = True,
    provider_factory=None,
) -> SeverAnalysisResult:
    current_name = store.current_context_name()
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

    return _start_analysis(
        store=store,
        source_name=source_name,
        criteria_name=criteria_name,
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
    return "\n".join(lines)


def _apply(store: MemoryStore, session: SeverSession) -> SeverSession:
    return execute_sever_apply(
        SeverApplyRequest(session=session),
        store=store,
    ).session


def _interactive_setup(store: MemoryStore) -> tuple[str, str, str, bool, bool] | None:
    names = tuple(store.list_context_names())
    granted = _granted_picker_state(store)
    receipt = choose_sever_setup(
        names,
        current=store.current_context_name(),
        virtual_names=granted.names,
        selectable_virtual_names=granted.selectable_names,
        annotations=granted.annotations,
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

    sessions = SeverSessionStore(store)
    navigation = ResolutionNavigation()
    while session.state == "REVIEWING":

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
        expected = sever_record_digest(session)
        if action.kind == "CHANGE_DESTINATION":
            if not allow_apply or action.destination is None:
                raise SeverCommandError("Review cannot change a Sever output location.")
            validate_destination(action.destination)
            changed = session.with_output_name(action.destination)
            if changed is not session:
                sessions.save(changed, expected_digest=expected)
                session = changed
            continue
        if action.kind == "ACCEPT":
            if not allow_apply:
                raise SeverCommandError("Review cannot apply a Sever output.")
            applied = _apply(store, session)
            sessions.save(applied, expected_digest=expected)
            session = applied
            break
        if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
            raise SeverCommandError("Unsupported Sever workbench action.")
        if action.comment.strip():
            session = session.select(action.item_uid, "CUSTOM", action.comment.strip())
        else:
            suffix = (action.option_uid or "").rpartition(":")[2]
            selection: SeverSelection = {
                "recommended": "RECOMMENDED",
                "as-written": "AS_WRITTEN",
                "forget": "FORGET",
            }.get(suffix)  # type: ignore[assignment]
            if selection is None:
                raise SeverCommandError("Unsupported Sever decision.")
            session = session.select(action.item_uid, selection)
        sessions.save(session, expected_digest=expected)
    return session


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
    source_descendants: Annotated[
        bool,
        typer.Option(
            "--source-descendants/--source-only",
            help="Include the Source root's readable descendant Contexts",
        ),
    ] = True,
    criteria_descendants: Annotated[
        bool,
        typer.Option(
            "--criteria-descendants/--criteria-only",
            help="Include the Criteria root's readable descendant Contexts",
        ),
    ] = True,
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
    store = MemoryStore()
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
        )
        session: SeverSession | None = None
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
                session = selected_session
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
            session = session_store.load(resume)
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
            source_name = source_name or store.current_context_name()
            if source_name is None:
                raise SeverCommandError(
                    "Starting Sever requires --source or a current Context."
                )
            analysis = _start_analysis(
                store=store,
                source_name=source_name,
                criteria_name=criteria_name,
                output_name=save_as,
                source_descendants=source_descendants,
                criteria_descendants=criteria_descendants,
            )
            session = analysis.session
            sever_prewarm_origin = (
                analysis.origin if analysis.origin != "PROVIDER" else None
            )
            session_store.save(session, expected_digest=None)

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
            expected = sever_record_digest(session)
            session = session.select(
                matches[0].uid,
                selections[normalized],
                (comment or "").strip(),
            )
            session_store.save(session, expected_digest=expected)

        if accept:
            expected = sever_record_digest(session)
            applied = _apply(store, session)
            if applied is not session:
                session_store.save(applied, expected_digest=expected)
            session = applied
        elif sys.stdin.isatty() and sys.stdout.isatty():
            session = _run_workbench(store, session)

        if sever_prewarm_origin:
            label = (
                "EXACT PREWARM"
                if sever_prewarm_origin == "EXACT_PREWARM"
                or (
                    sever_prewarm_origin == "EQUIVALENT_SCOPE_PREWARM"
                    and session.source.root_name == "task-3/local/personal-memory"
                    and session.criteria.root_name == "task-3/local/guardrails"
                    and session.source.include_descendants
                    and session.criteria.include_descendants
                )
                else "EQUIVALENT SCOPE PREWARM"
                if sever_prewarm_origin == "EQUIVALENT_SCOPE_PREWARM"
                else "PROJECTED PREWARM"
            )
            typer.echo(f"ANALYSIS · {label} · PROVIDER NOT CALLED")
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
