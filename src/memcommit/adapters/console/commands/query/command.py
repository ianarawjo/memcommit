"""Run one process-local Query over readable or authority-granted Sources."""

from typing import Annotated, Optional

import typer

import memcommit.application.ops as ops
from memcommit.adapters.console.commands.shared.command_progress import CommandProgress
from memcommit.adapters.console.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.application.authority.access import (
    ContextAccess,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.application.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryTarget,
)
from memcommit.application.operations.query.granted_runtime import (
    execute_granted_query_request,
    freeze_granted_query_targets,
    resolve_granted_query_target,
)
from memcommit.providers.find_query import (
    connect_ordinary_query_provider as connect_codex_chatgpt_provider,
    connect_query_route_provider as connect_query_provider,
)
from memcommit.adapters.interfaces.tui.operations.query import (
    run_query_workbench,
)
from memcommit.adapters.console.commands.shared.session_help import bind_session_help
from memcommit.adapters.console.commands.shared.readable_context_catalog import (
    freeze_readable_context_catalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.interfaces.console.text import (
    display_escape_text,
)
from memcommit.adapters.interfaces.console.terminal import is_interactive_terminal
from memcommit.adapters.interfaces.cli.query import (
    render_granted_query_response,
    render_ordinary_query_response,
    render_query_reference_response,
)
from memcommit.core.context import QueryContextRef
from memcommit.application.context_locator import is_relative_context_locator
from memcommit.core.context_targeting.presets import (
    ContextScopePreset,
    ContextTraversal,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.application.authority.derived_policy import authorize_combination
from memcommit.application.operations.search.answer_dialogue import FindAnswerCorpusTooLarge
from memcommit.application.operations.query.answer import OrdinaryQueryCorpusTooLarge
from memcommit.application.operations.profile.config import ProfileConfigError, load_profile_registry
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.subscription import QueryProviderError
from memcommit.application.operations.query.ordinary_application import OrdinaryQueryRequest
from memcommit.application.operations.query.ordinary_runtime import execute_ordinary_query
from memcommit.application.operations.query.reference_application import QueryReferenceRequest
from memcommit.application.operations.query.reference_runtime import execute_query_reference
from memcommit.application.operations.query.granted_source import (
    GrantedQuerySourceError,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.search.model import FindError


def _query_ordinary_context(
    store: MemoryStore,
    *,
    context_names: tuple[str | None, ...],
    current_name: str | None,
    question: str,
    traversal: ContextTraversal,
    all_contexts: bool = False,
) -> None:
    """Answer from the same frozen searchable frame used by ordinary Find."""
    accesses = tuple(
        resolve_context_access(
            store,
            context_name,
            current_name=current_name,
            required_permission="READ",
        )
        for context_name in context_names
    )
    if not accesses:
        raise ValueError("Select at least one readable Query Context.")
    target_names = tuple(access.display_name for access in accesses)
    if len(set(target_names)) != len(target_names):
        raise ValueError("Query Context roots must be distinct.")
    if all_contexts:
        # PROFILE is only a process-local shortcut. Freeze the concrete public
        # names once so provider work cannot reinterpret --all after current or
        # Profile state changes.
        catalog = freeze_profile_readable_context_catalog(store, accesses[0])
        target_names = tuple(catalog.list_context_names())
    elif len(accesses) == 1:
        # A granted public name is the semantic Source. Its local attachment is
        # authorization metadata and must never replace this exact target.
        catalog = freeze_readable_context_catalog(store, accesses[0])
    else:
        # Multiple explicit roots need the shared Profile catalog only as a
        # namespace. The request below still freezes exactly the named roots.
        catalog = freeze_profile_readable_context_catalog(store, accesses[0])
    frozen_accesses = tuple(catalog.access_for(name) for name in target_names)
    # Provider inference is a derived use even for one granted Source; combining
    # more than one ownership domain additionally requires COMBINE.
    authorize_combination(frozen_accesses)
    request = OrdinaryQueryRequest(
        question=question,
        target_names=target_names,
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
    query_target: GrantedQueryTarget | None = None,
    language: str,
    traversal: ContextTraversal | None = None,
) -> None:
    """Open one blank Query over frozen readable and public QUERY catalogs."""

    context_snapshot = ContextOperandSnapshot.capture(store)
    selected_name = (
        query_target.attachment_name
        if query_target is not None
        else context_snapshot.resolve_or_current(context_name)
    )
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

    def run_ordinary(request: OrdinaryQueryRequest):
        # The visible Profile/multi-target control combines Sources in one
        # semantic frame. Recheck DERIVE/COMBINE at the execution boundary,
        # after the exact checked names have been frozen.
        accesses = tuple(catalog.access_for(name) for name in request.target_names)
        if len(accesses) > 1:
            authorize_combination(accesses)
        return execute_ordinary_query(
            request,
            store=store,
            catalog=catalog,
            provider_factory=connect_codex_chatgpt_provider,
        )

    query_targets = freeze_granted_query_targets(store)
    if query_target is not None:
        # A granted operand may select a descendant route under a base Grant.
        # Replace that Grant's catalog row so the exact public route remains
        # visible and selected without fabricating a second Grant identity.
        query_targets = tuple(
            query_target if item.grant_uid == query_target.grant_uid else item
            for item in query_targets
        )
        if all(item.grant_uid != query_target.grant_uid for item in query_targets):
            query_targets = (*query_targets, query_target)
    initial_descendants = (
        traversal.include_descendants if traversal is not None else True
    )
    initial_embeds = traversal.follow_embeds if traversal is not None else True
    run_query_workbench(
        names,
        current_context=displayed_current,
        initial_context=access.display_name,
        query_targets=query_targets,
        run_ordinary=run_ordinary,
        run_granted=lambda request: execute_granted_query_request(
            request,
            store=store,
            provider_factory=lambda: connect_query_provider("codex_chatgpt"),
        ),
        initial_query_target=query_target,
        initial_include_descendants=initial_descendants,
        initial_follow_embeds=initial_embeds,
        initial_federate_descendants=initial_descendants,
        annotations=annotations,
        initial_language=language,
        help_binder=bind_session_help,
    )


def _query_granted_target(
    store: MemoryStore,
    *,
    target: GrantedQueryTarget,
    question: str,
    language: str,
    federate_descendants: bool,
) -> None:
    """Execute and render one already resolved public QUERY target."""

    progress = CommandProgress(
        "QUERY",
        "connecting provider",
        total=3,
    )
    try:
        progress.start()
        response = execute_granted_query_request(
            GrantedQueryRequest(
                target=target,
                question=question,
                language=language,
                federate_descendants=federate_descendants,
            ),
            store=store,
            provider_factory=lambda: connect_query_provider("codex_chatgpt"),
            observer=lambda stage: progress.update(
                {
                    "PREPARING_SOURCES": "preparing authorized sources",
                    "ANSWERING": "answering query",
                }[stage],
                step={"PREPARING_SOURCES": 2, "ANSWERING": 3}[stage],
            )
            if stage in {"PREPARING_SOURCES", "ANSWERING"}
            else None,
        )
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
        progress.close()
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def _resolve_positional_query_target(
    store: MemoryStore,
    selector: str,
    *,
    snapshot: ContextOperandSnapshot,
) -> ContextAccess | GrantedQueryTarget | None:
    """Resolve one accessible target before allowing question fallback.

    Only a genuinely absent bare name may fall back to an ordinary question.
    Relative locators and authority failures are explicit target intent and
    must remain visible errors instead of silently changing operation meaning.
    """

    canonical = snapshot.resolve(selector)
    ordinary: ContextAccess | None = None
    ordinary_error: FileNotFoundError | ProfileError | None = None
    try:
        ordinary = resolve_context_access(
            store,
            canonical,
            current_name=snapshot.current_name,
            required_permission="READ",
        )
    except (FileNotFoundError, ProfileError) as error:
        ordinary_error = error

    granted = resolve_granted_query_target(store, selector)
    if ordinary is not None and granted is not None:
        raise ValueError(
            f"Query target {selector!r} is available as both a readable Context "
            "and a query-only View; use --context/-c for the readable Context."
        )
    if ordinary is not None:
        return ordinary
    if granted is not None:
        return granted
    if isinstance(ordinary_error, ProfileError) or is_relative_context_locator(selector):
        assert ordinary_error is not None
        raise ordinary_error
    return None


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Existing readable Context or query-only View; when no accessible "
                "target matches and QUESTION is omitted, ask SELECTOR of the "
                "current Context"
            )
        ),
    ] = None,
    question: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Question for the selected Context or query-only View; omit it "
                "in a terminal to open that target in the Query workbench"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[list[str]],
        typer.Option(
            "--context",
            "-c",
            show_default=False,
            help=(
                "Readable Context root to answer from; repeat for multiple "
                "ordinary roots"
            ),
        ),
    ] = None,
    all_contexts: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Query all readable Contexts in the active Profile",
        ),
    ] = False,
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
        all_contexts
        or direct
        or recursive
        or include_descendants is not None
        or follow_embeds is not None
    )
    traversal_flags_supplied = (
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
    context_operands: tuple[str, ...] = (
        (context_name,)
        if isinstance(context_name, str)
        else tuple(context_name)
        if context_name
        else ()
    )
    if all_contexts and context_operands:
        typer.secho(
            "Query error: --all/-a cannot be combined with --context/-c.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if selector is None:
        if len(context_operands) > 1:
            typer.secho(
                "Query error: the interactive workbench accepts at most one "
                "initial --context; choose multiple Sources in its Scope control.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
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
                context_name=(context_operands[0] if context_operands else None),
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
    if all_contexts:
        if question is not None:
            typer.secho(
                "Query error: --all/-a applies only to the ordinary one-question "
                "form, not a query-only view.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        if language != "en":
            typer.secho(
                "Query error: --language applies only to a query-only view.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        try:
            context_snapshot = ContextOperandSnapshot.capture(store)
            _query_ordinary_context(
                store,
                context_names=(None,),
                current_name=context_snapshot.current_name,
                question=selector,
                traversal=traversal,
                all_contexts=True,
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
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        resolved_context_names = tuple(
            context_snapshot.resolve(operand) for operand in context_operands
        )
        if question is not None and not question.strip():
            raise ValueError("Question must be non-empty.")
        if resolved_context_names and question is None:
            if len(resolved_context_names) == 1:
                try:
                    resolve_context_access(
                        store,
                        resolved_context_names[0],
                        current_name=context_snapshot.current_name,
                        required_permission="READ",
                    )
                except (FileNotFoundError, ProfileError) as read_error:
                    granted_target = resolve_granted_query_target(
                        store,
                        resolved_context_names[0],
                    )
                    if granted_target is None:
                        raise read_error
                    _query_granted_target(
                        store,
                        target=granted_target,
                        question=selector,
                        language=language,
                        federate_descendants=traversal.include_descendants,
                    )
                    return
            if language != "en":
                raise ValueError("--language applies only to a query-only view.")
            _query_ordinary_context(
                store,
                context_names=resolved_context_names,
                current_name=context_snapshot.current_name,
                question=selector,
                traversal=traversal,
            )
            return

        if not resolved_context_names:
            positional_target = _resolve_positional_query_target(
                store,
                selector,
                snapshot=context_snapshot,
            )
            if isinstance(positional_target, ContextAccess):
                if question is None:
                    if not is_interactive_terminal():
                        raise ValueError(
                            "QUESTION is required outside a terminal for a selected "
                            "Context. In a terminal, omit it to open the Query "
                            "workbench."
                        )
                    _open_query_workbench(
                        store,
                        context_name=positional_target.display_name,
                        language=language,
                        traversal=(traversal if traversal_flags_supplied else None),
                    )
                else:
                    if language != "en":
                        raise ValueError(
                            "--language applies only to a query-only view."
                        )
                    _query_ordinary_context(
                        store,
                        context_names=(positional_target.display_name,),
                        current_name=context_snapshot.current_name,
                        question=question,
                        traversal=traversal,
                    )
                return
            if isinstance(positional_target, GrantedQueryTarget):
                if question is None:
                    if not is_interactive_terminal():
                        raise ValueError(
                            "QUESTION is required outside a terminal for a selected "
                            "Query View. In a terminal, omit it to open the Query "
                            "workbench."
                        )
                    _open_query_workbench(
                        store,
                        context_name=None,
                        query_target=positional_target,
                        language=language,
                        traversal=(traversal if traversal_flags_supplied else None),
                    )
                else:
                    _query_granted_target(
                        store,
                        target=positional_target,
                        question=question,
                        language=language,
                        federate_descendants=traversal.include_descendants,
                    )
                return
            if question is None:
                if language != "en":
                    raise ValueError("--language applies only to a query-only view.")
                _query_ordinary_context(
                    store,
                    context_names=(None,),
                    current_name=context_snapshot.current_name,
                    question=selector,
                    traversal=traversal,
                )
                return
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
    if len(resolved_context_names) > 1:
        typer.secho(
            "Query error: repeated --context applies only to the ordinary "
            "one-question form.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    try:
        anchor_name = (
            resolved_context_names[0]
            if resolved_context_names
            else context_snapshot.current_name
        )
        if not anchor_name:
            raise RuntimeError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        if not store.context_exists(anchor_name):
            # Legacy two-positional routing needs a local control-plane anchor.
            # Keep it separate from the already classified semantic Source so
            # attachment recovery can never retarget an ordinary Query.
            navigation_registry = load_profile_registry()
            attachment_identities = {
                (
                    grant.attachment_context_uid,
                    grant.attachment_context_name,
                )
                for grant in navigation_registry.grants
                if grant.grantee_profile_uid == navigation_registry.active.uid
                and (
                    anchor_name == grant.public_name
                    or anchor_name.startswith(grant.public_name + "/")
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
            anchor_name = attachment_name
        ctx = store.load(anchor_name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
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
        assert question is not None
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
    route_selector = selector
    try:
        registry = load_profile_registry()
        matching_grants = [
            grant
            for grant in registry.grants
            if grant.grantee_profile_uid == registry.active.uid
            and grant.attachment_context_uid == ctx.uid
            and grant.attachment_context_name == anchor_name
            and (
                selector == grant.public_name
                or selector.startswith(grant.public_name + "/")
            )
        ]
        if matching_grants:
            routed_grants = matching_grants
        else:
            routed_grants = [
                grant
                for grant in registry.grants
                if grant.grantee_profile_uid == registry.active.uid
                and grant.attachment_context_uid == ctx.uid
                and grant.attachment_context_name == anchor_name
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

    assert question is not None
    _query_granted_target(
        store,
        target=GrantedQueryTarget(
            grant_uid=effective_grant.uid,
            public_name=route_selector,
            attachment_name=anchor_name,
        ),
        question=question,
        language=language,
        federate_descendants=traversal.include_descendants,
    )
