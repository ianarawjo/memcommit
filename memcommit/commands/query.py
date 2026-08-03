"""Ask a question of an opaque or authority-granted query view."""

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.tui_primitives import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.context import QueryContextRef
from memcommit.profile_config import ProfileConfigError, load_profile_registry
from memcommit.profiles import (
    ProfileError,
    authority_grant_snapshot_lock,
    resolve_granted_context_view,
)
from memcommit.query_provider import QueryProviderError, connect_query_provider
from memcommit.query_sessions import (
    QuerySessionError,
    QuerySessionStore,
    load_authority_query_source,
    query_session_binding,
    render_session_question,
    validate_query_session_name,
)
from memcommit.store import MemoryStore


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(help="Query-only Context name or reference UID/prefix"),
    ] = None,
    question: Annotated[
        Optional[str],
        typer.Argument(help="Question to answer from the concealed source"),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Parent context containing the query-only reference",
        ),
    ] = None,
    language: Annotated[
        str,
        typer.Option(
            "--language",
            "-l",
            help=(
                "Concealed source language to query; exact translations "
                "must cover the whole source"
            ),
        ),
    ] = "en",
    session_name: Annotated[
        Optional[str],
        typer.Option(
            "--session",
            help=(
                "Save and replay visible Q/A in the active task Profile; "
                "the grant must allow SESSION_LOG"
            ),
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="List saved task-owned query transcripts without opening sources",
        ),
    ] = False,
    show_session_name: Annotated[
        Optional[str],
        typer.Option(
            "--show-session",
            help="Show one saved task-owned Q/A transcript",
        ),
    ] = None,
) -> None:
    store = MemoryStore()
    if sessions or show_session_name is not None:
        if sessions and show_session_name is not None:
            typer.secho(
                "Error: choose either --sessions or --show-session.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if (
            selector is not None
            or question is not None
            or context_name is not None
            or session_name is not None
            or language != "en"
        ):
            typer.secho(
                "Error: transcript inspection cannot be combined with a query.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        session_store = QuerySessionStore(store.store_dir)
        try:
            if sessions:
                saved = session_store.list_sessions()
                if not saved:
                    typer.echo("No saved query sessions.")
                    return
                for session in saved:
                    typer.echo(
                        f"{session.name} · view={session.binding.requested_name} · "
                        f"language={session.binding.language} · "
                        f"{len(session.turns)} turn(s) · revision {session.revision}"
                    )
                return
            assert show_session_name is not None
            session = session_store.load(show_session_name)
        except (OSError, QuerySessionError, ValueError) as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.secho(
            f"Query session: {display_escape_text(session.name)}",
            bold=True,
        )
        typer.echo(
            "View: "
            + display_escape_text(session.binding.requested_name)
            + " · language="
            + display_escape_text(session.binding.language)
        )
        if not session.turns:
            typer.echo("\n(no turns)")
            return
        for index, turn in enumerate(session.turns, start=1):
            typer.secho(f"\nQ{index}", bold=True)
            typer.echo(safe_terminal_text(turn.question))
            typer.secho(f"A{index}", bold=True)
            typer.echo(safe_terminal_text(turn.answer))
        return

    if selector is None or question is None:
        typer.secho(
            "Error: provide SELECTOR and QUESTION, or inspect --sessions.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        selected_name = context_snapshot.resolve_or_current(context_name)
        if not selected_name:
            raise RuntimeError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        ctx = store.load(selected_name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if not question.strip():
        typer.secho(
            "Error: question must be non-empty.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if session_name is not None:
        try:
            session_name = validate_query_session_name(session_name)
        except QuerySessionError as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    resolution_error: KeyError | ValueError | None = None
    try:
        item = ops.resolve(ctx, selector)
    except (KeyError, ValueError) as error:
        item = None
        resolution_error = error

    if isinstance(item, QueryContextRef):
        if session_name is not None:
            typer.secho(
                "Error: --session is available only for authority-granted "
                "query views with SESSION_LOG permission.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        _query_legacy(store, item, question, language=language)
        return

    # Grant routing metadata is public control-plane state. Inspecting it does
    # not open authority content and avoids authenticating for an ordinary
    # item or a selector that has no query-view route at all.
    try:
        registry = load_profile_registry()
        routed_grants = [
            grant
            for grant in registry.grants
            if grant.grantee_profile_uid == registry.active.uid
            and grant.attachment_context_uid == ctx.uid
            and grant.attachment_context_name == selected_name
            and (
                selector == grant.public_name
                or selector.startswith(grant.public_name + "/")
            )
        ]
    except ProfileConfigError as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if not routed_grants:
        message = (
            str(resolution_error)
            if resolution_error is not None
            else f"'{selector}' is not a query-only Context."
        )
        typer.secho(
            f"Error: {display_escape_text(message)}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    effective_grant = max(
        routed_grants,
        key=lambda grant: len(grant.public_name.split("/")),
    )
    required_permission = "SESSION_LOG" if session_name is not None else "QUERY"
    if required_permission not in effective_grant.permissions:
        typer.secho(
            f"Query error: Grant {effective_grant.uid[:8]} does not allow "
            f"{required_permission.lower()} access to "
            f"{display_escape_text(selector)!r}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    # The temporary authority provider is known before any authority Context
    # is opened. Authentication therefore remains the query-data boundary.
    try:
        provider = connect_query_provider("codex_chatgpt")
    except QueryProviderError as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        view = resolve_granted_context_view(
            selector,
            attachment_name=selected_name,
            required_permission=required_permission,
        )
    except (ProfileConfigError, ProfileError) as error:
        if str(error) == f"Granted view {selector!r} does not exist.":
            message = f"'{selector}' is not a query-only Context."
            prefix = "Error"
        else:
            message = str(error)
            prefix = "Query error"
        typer.secho(
            f"{prefix}: {display_escape_text(message)}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        source = load_authority_query_source(view, language=language)
        binding = query_session_binding(view, source, language=language)
        session_store = QuerySessionStore(store.store_dir)
        saved_session = None
        expected_session_digest = None
        provider_question = question
        if session_name is not None:
            saved_session, expected_session_digest = session_store.load_or_start(
                session_name,
                binding,
            )
            provider_question = render_session_question(
                saved_session.turns,
                question,
            )
        answer = provider.query(source.name, source.content, provider_question)

        # Re-resolve both permission and source after the provider call for
        # saved and one-shot queries. Keep the registry lock through transcript
        # publication and terminal output so a revocation cannot win between
        # the final authority check and disclosure.
        with authority_grant_snapshot_lock() as current_registry:
            current_view = resolve_granted_context_view(
                selector,
                attachment_name=selected_name,
                required_permission=required_permission,
                registry=current_registry,
            )
            current_source = load_authority_query_source(
                current_view,
                language=language,
            )
            current_binding = query_session_binding(
                current_view,
                current_source,
                language=language,
            )
            if current_binding != binding:
                raise QuerySessionError(
                    "The granted query view changed while the provider was "
                    "answering; the answer was not published."
                )
            if saved_session is not None:
                session_store.append_turn(
                    saved_session,
                    expected_record_digest=expected_session_digest,
                    question=question,
                    answer=answer,
                )
            typer.echo(safe_terminal_text(answer))
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        QuerySessionError,
        ValueError,
    ) as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

def _query_legacy(
    store: MemoryStore,
    item: QueryContextRef,
    question: str,
    *,
    language: str,
) -> None:
    """Preserve the original unsaved QueryContextRef provider boundary."""

    # Authenticate the provider before opening the concealed local source.
    try:
        provider = connect_query_provider(item.provider)
    except QueryProviderError as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        source = store.load_query_source(
            item.target_source_uid,
            expected_name=item.name,
            language=language,
        )
        answer = provider.query(source.name, source.content, question)
    except (
        FileNotFoundError,
        ValueError,
        QueryProviderError,
    ) as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(safe_terminal_text(answer))
