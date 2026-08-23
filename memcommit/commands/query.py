"""Run one process-local Query over readable or authority-granted Sources."""

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryTarget,
)
from memcommit.operations.query.granted_runtime import (
    execute_granted_query_request,
    freeze_granted_query_targets,
)
from memcommit.infrastructure.providers.find_query import (
    connect_ordinary_query_provider as connect_codex_chatgpt_provider,
    connect_query_route_provider as connect_query_provider,
)
from memcommit.interfaces.tui.operations.query import (
    run_query_workbench,
)
from memcommit.commands.session_help import bind_session_help
from memcommit.commands.readable_context_catalog import (
    freeze_readable_context_catalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.console.terminal import is_interactive_terminal
from memcommit.interfaces.cli.query import (
    render_granted_query_response,
    render_ordinary_query_response,
    render_query_reference_response,
    split_query_memory_selector,
)
from memcommit.context import QueryContextRef
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    ContextTraversal,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.find_answer_dialogue import FindAnswerCorpusTooLarge
from memcommit.ordinary_query_answer import OrdinaryQueryCorpusTooLarge
from memcommit.profile_config import ProfileConfigError, load_profile_registry
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError
from memcommit.operations.query.ordinary_application import OrdinaryQueryRequest
from memcommit.operations.query.ordinary_runtime import execute_ordinary_query
from memcommit.operations.query.reference_application import QueryReferenceRequest
from memcommit.operations.query.reference_runtime import execute_query_reference
from memcommit.operations.query.granted_source import (
    GrantedQuerySourceError,
    load_authority_query_catalog,
)
from memcommit.store import MemoryStore
from memcommit.search import FindError


def _query_ordinary_context(
    store: MemoryStore,
    *,
    context_name: str,
    question: str,
    traversal: ContextTraversal,
) -> None:
    """Answer from the same frozen searchable frame used by ordinary Find."""
    access = resolve_context_access(
        store,
        context_name,
        current_name=store.current_context_name(),
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(store, access)
    request = OrdinaryQueryRequest(
        question=question,
        target_names=(access.display_name,),
        include_descendants=traversal.include_descendants,
        follow_embeds=traversal.follow_embeds,
    )
    with CommandProgress(
        "QUERY",
        "connecting provider",
        total=2,
    ) as progress:
        response = execute_ordinary_query(
            request,
            store=store,
            catalog=catalog,
            provider_factory=connect_codex_chatgpt_provider,
            observer=lambda stage: (
                progress.update(
                    "answering question",
                    step=2,
                )
                if stage == "ANSWERING"
                else None
            ),
        )
    render_ordinary_query_response(response)


def _open_query_workbench(
    store: MemoryStore,
    *,
    context_name: str | None,
    language: str,
) -> None:
    """Open one blank Query over frozen readable and public QUERY catalogs."""

    context_snapshot = ContextOperandSnapshot.capture(store)
    selected_name = context_snapshot.resolve_or_current(context_name)
    access = resolve_context_access(
        store,
        selected_name,
        current_name=context_snapshot.current_name,
        required_permission="READ",
    )
    catalog = freeze_profile_readable_context_catalog(store, access)
    names = tuple(catalog.list_context_names())
    displayed_current = (
        context_snapshot.current_name
        if context_snapshot.current_name in names
        else access.display_name
    )
    annotations = {
        name: context_access_display_facts(catalog.access_for(name))
        for name in names
        if catalog.access_for(name).is_granted
    }
    run_query_workbench(
        names,
        current_context=displayed_current,
        initial_context=access.display_name,
        query_targets=freeze_granted_query_targets(store),
        run_ordinary=lambda request: execute_ordinary_query(
            request,
            store=store,
            catalog=catalog,
            provider_factory=connect_codex_chatgpt_provider,
        ),
        run_granted=lambda request: execute_granted_query_request(
            request,
            store=store,
            provider_factory=lambda: connect_query_provider("codex_chatgpt"),
            load_catalog=load_authority_query_catalog,
        ),
        annotations=annotations,
        initial_language=language,
        help_binder=bind_session_help,
    )


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Question for the selected ordinary Context, or a query-only "
                "Context name, optional #HANDLE, or legacy reference UID/prefix; "
                "omit in a terminal to open the interactive Query workbench"
            )
        ),
    ] = None,
    question: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Question for a query-only view; omit it to ask SELECTOR as "
                "a question of ordinary data or browse a recognized opaque view"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help=(
                "Ordinary Context to answer from, or parent Context containing "
                "the query-only reference"
            ),
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
    include_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--descendants/--context-only",
            help="Control lexical descendant reach for an ordinary query",
        ),
    ] = None,
    follow_embeds: Annotated[
        Optional[bool],
        typer.Option(
            "--follow-embeds/--exclude-embeds",
            help="Control embedded Context traversal for an ordinary query",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Query only the selected Context root"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants and follow embedded Contexts",
        ),
    ] = False,
) -> None:
    scope_flags_supplied = (
        direct
        or recursive
        or include_descendants is not None
        or follow_embeds is not None
    )
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(
            preset=preset,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
        )
    except (TypeError, ValueError) as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore()
    if selector is None:
        if scope_flags_supplied:
            typer.secho(
                "Query error: scope flags require a one-shot SELECTOR; "
                "the interactive workbench owns its visible scope controls.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        if not is_interactive_terminal():
            typer.secho(
                "Query error: SELECTOR is required outside a terminal. In a "
                "terminal, run 'mem query' to open the interactive Query "
                "workbench.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            _open_query_workbench(
                store,
                context_name=context_name,
                language=language,
            )
        except (
            FileNotFoundError,
            FindAnswerCorpusTooLarge,
            OrdinaryQueryCorpusTooLarge,
            FindError,
            OSError,
            ProfileConfigError,
            ProfileError,
            QueryProviderError,
            GrantedQuerySourceError,
            RuntimeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Query error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return
    candidate_route_selector, candidate_memory_handle = split_query_memory_selector(
        selector
    )
    route_selector = selector
    memory_handle = None
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        selected_name = context_snapshot.resolve_or_current(context_name)
        if not selected_name:
            raise RuntimeError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        if not store.context_exists(selected_name):
            # A READ-granted current view is not a local Context. Query routes
            # remain attached to its owned workspace, so recover that public
            # control-plane anchor without opening authority content.
            navigation_registry = load_profile_registry()
            attachment_identities = {
                (
                    grant.attachment_context_uid,
                    grant.attachment_context_name,
                )
                for grant in navigation_registry.grants
                if grant.grantee_profile_uid == navigation_registry.active.uid
                and (
                    selected_name == grant.public_name
                    or selected_name.startswith(grant.public_name + "/")
                )
                and store.context_exists(grant.attachment_context_name)
            }
            if len(attachment_identities) != 1:
                raise RuntimeError(
                    "The current granted view has no unique local query anchor."
                )
            attachment_uid, attachment_name = next(iter(attachment_identities))
            attachment = store.load_direct(attachment_name)
            if attachment.uid != attachment_uid:
                raise RuntimeError("The current granted view's query anchor changed.")
            selected_name = attachment_name
        ctx = store.load(selected_name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if question is not None and not question.strip():
        typer.secho(
            "Error: question must be non-empty.",
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
        if question is None:
            typer.secho(
                "Error: legacy query-only references require a QUESTION; "
                "opaque Memory browsing is available for authority grants.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        progress = CommandProgress(
            "QUERY",
            "connecting provider",
            total=2,
        )
        try:
            progress.start()
            response = execute_query_reference(
                QueryReferenceRequest(
                    source_uid=item.target_source_uid,
                    source_name=item.name,
                    provider_name=item.provider,
                    question=question,
                    language=language,
                ),
                store=store,
                provider_factory=connect_query_provider,
                observer=lambda stage: (
                    progress.update("answering query", step=2)
                    if stage == "ANSWERING"
                    else None
                ),
            )
            progress.close()
        except (
            FileNotFoundError,
            ValueError,
            QueryProviderError,
        ) as error:
            progress.close()
            typer.secho(
                f"Query error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        render_query_reference_response(response)
        return

    # Grant routing metadata is public control-plane state. Inspecting it does
    # not open authority content and avoids authenticating for an ordinary
    # item or a selector that has no query-view route at all.
    try:
        registry = load_profile_registry()
        matching_grants = [
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
        if matching_grants:
            routed_grants = matching_grants
        else:
            route_selector = candidate_route_selector
            memory_handle = candidate_memory_handle
            routed_grants = [
                grant
                for grant in registry.grants
                if grant.grantee_profile_uid == registry.active.uid
                and grant.attachment_context_uid == ctx.uid
                and grant.attachment_context_name == selected_name
                and (
                    route_selector == grant.public_name
                    or route_selector.startswith(grant.public_name + "/")
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
        if question is None:
            if language != "en":
                typer.secho(
                    "Error: --language applies only to a query-only view.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            try:
                _query_ordinary_context(
                    store,
                    context_name=selected_name,
                    question=selector,
                    traversal=traversal,
                )
            except (
                FileNotFoundError,
                FindAnswerCorpusTooLarge,
                OrdinaryQueryCorpusTooLarge,
                FindError,
                OSError,
                ProfileConfigError,
                ProfileError,
                QueryProviderError,
                RuntimeError,
                ValueError,
            ) as error:
                typer.secho(
                    f"Query error: {display_escape_text(str(error))}",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            return
        message = (
            str(resolution_error)
            if resolution_error is not None
            else f"'{route_selector}' is not a query-only Context."
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
    if "QUERY" not in effective_grant.permissions:
        typer.secho(
            f"Query error: Grant {effective_grant.uid[:8]} does not allow "
            "query access to "
            f"{display_escape_text(route_selector)!r}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    progress = (
        CommandProgress(
            "QUERY",
            "connecting provider",
            total=3,
        )
        if question is not None
        else None
    )
    try:
        if progress is not None:
            progress.start()
        response = execute_granted_query_request(
            GrantedQueryRequest(
                target=GrantedQueryTarget(
                    grant_uid=effective_grant.uid,
                    public_name=route_selector,
                    attachment_name=selected_name,
                ),
                question=question,
                language=language,
                memory_handle=memory_handle,
                federate_descendants=traversal.include_descendants,
            ),
            store=store,
            provider_factory=lambda: connect_query_provider("codex_chatgpt"),
            observer=(
                (
                    lambda stage: progress.update(
                        {
                            "PREPARING_SOURCES": "preparing authorized sources",
                            "ANSWERING": "answering query",
                        }[stage],
                        step={"PREPARING_SOURCES": 2, "ANSWERING": 3}[stage],
                    )
                    if stage in {"PREPARING_SOURCES", "ANSWERING"}
                    else None
                )
                if progress is not None
                else None
            ),
            load_catalog=load_authority_query_catalog,
        )
        if progress is not None:
            progress.close()
        render_granted_query_response(response)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        GrantedQuerySourceError,
        ValueError,
    ) as error:
        if progress is not None:
            progress.close()
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
