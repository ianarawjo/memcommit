"""Create, review, and materialize one Source × Criteria Sever session."""

from __future__ import annotations

import sys
from typing import Annotated, Literal, Optional

import typer

from memcommit.application.context_access.access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    choose_session,
)
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.commands.sever.sessions import (
    list_sever_session_catalog,
    reload_selected_sever_session,
)
from memcommit.application.context_access.granted_context_navigation import (
    freeze_granted_context_navigation,
)
from memcommit.adapters.console.coordination.endpoint_operand import (
    choose_endpoint_operand,
)
from memcommit.adapters.console.terminal.components.context_picker import (
    context_memory_rows,
)
from memcommit.adapters.console.commands.sever.endpoint_setup import (
    choose_sever_setup,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.providers.errors import QueryProviderError
from memcommit.providers.connection import connect_semantic_provider
from memcommit.application.operations.sever.model import (
    SeverError,
    SeverSelection,
    SeverSession,
)
from memcommit.application.operations.sever.application import (
    SeverAnalysisProgress,
    SeverAnalysisRequest,
    SeverAnalysisResult,
    SeverApplicationError,
    SeverApplyRequest,
    SeverDecisionRequest,
    SeverPersistedApplyRequest,
    SeverSessionSnapshot,
)
from memcommit.application.operations.sever.provider import SeverProviderError
from memcommit.application.operations.sever.inputs import capture_sever_binding
from memcommit.application.operations.sever.runtime import (
    execute_sever_analysis,
    execute_sever_apply,
    execute_sever_session_apply,
    execute_sever_session_decision,
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

    if event.stage == "CONNECTING_PROVIDER":
        progress.update("connecting provider", step=2)
    elif event.stage == "ANALYZING":
        progress.update(
            f"analyzing {event.source_count} source x {event.criteria_count} criteria",
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
        source_locator=source_access.access_name,
        criteria_locator=criteria_access.access_name,
        output_name=output_name,
        source_include_descendants=source_descendants,
        criteria_include_descendants=criteria_descendants,
    )

    def freeze_and_analyze(progress) -> SeverAnalysisResult:
        return execute_sever_analysis(
            request,
            store=store,
            provider_factory=provider_factory or connect_semantic_provider,
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
    candidates = freeze_profile_context_access_candidates(
        store,
        current_name=snapshot.current_name,
    )
    return _start_analysis(
        store=store,
        current_name=snapshot.current_name,
        source_name=resolve_existing_context_access(
            store,
            source_name,
            current_name=snapshot.current_name,
            required_permission="READ",
            candidates=candidates,
        ).name,
        criteria_name=resolve_existing_context_access(
            store,
            criteria_name,
            current_name=snapshot.current_name,
            required_permission="READ",
            candidates=candidates,
        ).name,
        output_name=output_name,
        source_descendants=source_descendants,
        criteria_descendants=criteria_descendants,
        provider_factory=provider_factory,
    ).session


def render_sever(session: SeverSession) -> str:
    self_save = session.save_mode == "SELF_SAVE"
    source_context_count = len(session.source.contexts)
    lines = [
        f"SEVER · {session.state} · " + ("IN PLACE" if self_save else "OTHER-SAVE"),
        f"SOURCE · {safe_terminal_text(session.source.root_name)} · "
        f"{'INCLUDE DESCENDANTS' if session.source.include_descendants else 'THIS CONTEXT ONLY'} · "
        f"{len(session.source.memories)} Memories",
        f"CRITERIA · {safe_terminal_text(session.criteria.root_name)} · "
        f"{'INCLUDE DESCENDANTS' if session.criteria.include_descendants else 'THIS CONTEXT ONLY'}",
        (
            f"APPLY · {source_context_count} SOURCE CONTEXT"
            f"{'S' if source_context_count != 1 else ''} · "
            + ("UPDATED IN PLACE" if session.state == "APPLIED" else "UPDATE IN PLACE")
            if self_save
            else f"OUTPUT · {safe_terminal_text(session.output_name)} · "
            + ("CREATED LOCALLY" if session.state == "APPLIED" else "READY TO CREATE")
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
            else (
                candidate.custom_content
                if candidate.selection == "CUSTOM"
                else (
                    source.content
                    if candidate.selection == "AS_WRITTEN"
                    else candidate.proposed_content
                )
            )
        )
        lines.extend(
            [
                f"  {index}. [{candidate.uid[:8]}] {label}",
                f"     SOURCE · {safe_terminal_text(source.content)}",
                f"     {'AFTER' if self_save else 'RESULT'} · {safe_terminal_text(result)}",
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
                "Apply updates each selected Source Context at its existing location."
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
    if self_save:
        checkpoint_count = len(session.application.checkpoints) or 1
        lines = [
            f"SEVER APPLIED · {session.source.root_name} · IN PLACE",
            f"CONTEXTS · {checkpoint_count} UPDATED IN PLACE",
        ]
    else:
        lines = [
            f"SEVER APPLIED · {session.source.root_name} → {session.output_name}",
            "SAVE MODE · OTHER-SAVE",
        ]
    lines.extend(
        [
            f"DECISIONS · KEEP {len(session.application.result_memory_uids)} · FORGET {forgotten}",
            "SOURCE · UPDATED" if self_save else "RESULT · CREATED SEPARATELY",
            f"RECEIPT · {session.uid}",
            f"CHECKPOINT · {session.application.checkpoint_uid}",
            f"REVIEW · mem review sever --session {session.uid}",
            "RECOVERY · mem undo",
        ]
    )
    return "\n".join(lines)


def render_sever_incomplete_receipt(session: SeverSession) -> str:
    """Return saved Sever state without repeating its candidate report."""

    required = 0  # Analysis already supplied one complete treatment per Source Memory.
    if session.save_mode == "SELF_SAVE":
        route = f"{session.source.root_name} × {session.criteria.root_name} · IN PLACE"
        destination = (
            f"SOURCE · UNCHANGED · {len(session.source.contexts)} CONTEXT"
            f"{'S' if len(session.source.contexts) != 1 else ''} UPDATE ON APPLY"
        )
    else:
        route = f"{session.source.root_name} → {session.output_name}"
        destination = f"OUTPUT · {session.output_name} · READY TO CREATE"
    return "\n".join(
        [
            f"SEVER {'NEEDS INPUT' if required else 'READY'} · {route}",
            f"JUDGMENTS · REQUIRED {required}",
            destination,
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


def _interactive_setup(store: MemoryStore) -> tuple[str, str, bool, bool] | None:
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
        return context_memory_rows(GrantedReadStore(access).load(access.access_name))

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
        route = (
            f"{item.source.root_name} × {item.criteria.root_name} · IN PLACE"
            if item.save_mode == "SELF_SAVE"
            else f"{item.source.root_name} × {item.criteria.root_name} → {item.output_name}"
        )
        typer.echo(f"{item.uid} · {item.state} · {route}")


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


def _run_preview(store: MemoryStore, session: SeverSession) -> SeverSession:
    from memcommit.adapters.console.commands.sever.preview import run_sever_preview

    snapshot = execute_sever_session_open(session.uid, store=store)
    if snapshot.session != session:
        raise SeverCommandError("The Sever result changed before Preview. Reopen it.")
    if session.state == "APPLIED":
        return session

    def apply_preview():
        # The application snapshot token binds the displayed treatments to Apply.
        return execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=snapshot), store=store,
        ).snapshot.session

    return run_sever_preview(session, apply_preview=apply_preview) or session


def _resolve_endpoint_syntax(
    endpoints: list[str] | None,
    *,
    source_name: str | None,
    criteria_name: str | None,
) -> tuple[str | None, str | None]:
    """Normalize positional roles and their compatibility options."""

    positional = tuple(endpoints or ())
    if len(positional) > 2:
        raise SeverCommandError(
            "expected exactly two positional Contexts: SOURCE CRITERIA. "
            "Sever updates the selected Source scope in place."
        )
    resolved = [source_name, criteria_name]
    role_options = (
        "--source/--from",
        "--criteria/--against",
    )
    role_names = ("SOURCE", "CRITERIA")
    for index, value in enumerate(positional):
        if resolved[index] is not None:
            raise SeverCommandError(
                f"{role_names[index]} was supplied both positionally and with "
                f"{role_options[index]}."
            )
        resolved[index] = value
    return resolved[0], resolved[1]


def cmd(
    contexts: Annotated[
        list[str] | None,
        typer.Argument(
            help="SOURCE and CRITERIA Contexts; Source owners are updated in place",
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
        typer.Option("--comment", help="Exact retained content when --choice custom"),
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
            help="Apply the reviewed Sever session",
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
        source_name, criteria_name = _resolve_endpoint_syntax(
            contexts,
            source_name=source_option,
            criteria_name=criteria_option,
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
            and resume is None
        ):
            raise SeverCommandError(
                "Scope flags require an explicit --source/--criteria setup; "
                "interactive setup owns its visible ranges."
            )
        session: SeverSession | None = None
        snapshot: SeverSessionSnapshot | None = None
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
            if any(value is not None for value in (source_name, criteria_name)):
                raise SeverCommandError(
                    "--resume cannot be combined with Source or Criteria operands."
                )
            snapshot = execute_sever_session_open(resume, store=store)
            session = snapshot.session
        else:
            if start_new_from_sessions or source_name is None and criteria_name is None:
                if not interactive:
                    typer.echo(
                        "No Sever setup supplied. Use SOURCE CRITERIA, or run in a TTY."
                    )
                    return
                setup = _interactive_setup(store)
                if setup is None:
                    typer.echo("Sever setup cancelled. No session created.")
                    return
                (
                    source_name,
                    criteria_name,
                    source_descendants,
                    criteria_descendants,
                ) = setup
            if criteria_name is None:
                raise SeverCommandError("Starting Sever requires CRITERIA.")
            if source_name is None and context_snapshot.current_name is None:
                raise SeverCommandError(
                    "Starting Sever requires SOURCE or a current Context."
                )
            context_candidates = freeze_profile_context_access_candidates(
                store,
                current_name=context_snapshot.current_name,
            )
            source_name = resolve_existing_context_access(
                store,
                source_name,
                current_name=context_snapshot.current_name,
                required_permission="READ",
                candidates=context_candidates,
            ).name
            criteria_name = resolve_existing_context_access(
                store,
                criteria_name,
                current_name=context_snapshot.current_name,
                required_permission="READ",
                candidates=context_candidates,
            ).name
            if source_descendants is None or criteria_descendants is None:
                raise SeverCommandError("Sever scope resolution produced no range.")
            analysis = _start_analysis(
                store=store,
                current_name=context_snapshot.current_name,
                source_name=source_name,
                criteria_name=criteria_name,
                # Console Sever is always in place. Reuse the canonical Source
                # captured from this command-start snapshot as the internal
                # post-image identity; it is not a user-selectable endpoint.
                output_name=source_name,
                source_descendants=source_descendants,
                criteria_descendants=criteria_descendants,
            )
            stored = execute_sever_session_start(analysis, store=store)
            snapshot = stored.snapshot
            session = snapshot.session
        if session is None or snapshot is None:
            raise SeverCommandError("Sever session lifecycle produced no snapshot.")

        if candidate is not None or choice is not None or comment is not None:
            if candidate is None or choice is None:
                raise SeverCommandError(
                    "A scripted decision requires --candidate and --choice."
                )
            if expect_session is not None and expect_session != snapshot.version_token:
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
            session = _run_preview(store, session)

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
