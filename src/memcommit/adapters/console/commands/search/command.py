"""Search CLI options, route selection, and terminal error translation."""

import sys
from typing import Annotated, NoReturn, Optional

import typer

from memcommit.adapters.console.commands.search.execution import run_static_search
from memcommit.adapters.console.commands.search.preparation import prepare_search
from memcommit.adapters.console.commands.search.receipt import render_search_receipt
from memcommit.adapters.console.commands.search.workbench.launcher import (
    open_search_workbench,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextFromSelectionError,
)
from memcommit.application.operations.search.application import SearchRequest
from memcommit.application.operations.search.errors import SearchError
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import QueryProviderError


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _exit_error(
    error: Exception, *, prefix: str = "Search error", code: int = 1
) -> NoReturn:
    typer.secho(
        f"{prefix}: {display_escape_text(str(error))}",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(code)


def cmd(
    query: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=(
                "Natural-language query; omit in a terminal to open the "
                "interactive search with compact exact-Context Scope, "
                "Browse-only Profile/multiple selection, independent range "
                "and Embed choices, and checked-result COPY/REFERENCE/EMBED Save"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[list[str]],
        typer.Option(
            "--context",
            "-c",
            show_default=False,
            help=(
                "Context root to search; repeat for multiple roots "
                "(defaults to current)"
            ),
        ),
    ] = None,
    all_contexts: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Search all readable Contexts in the active Profile",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum matches to return (1-20)",
        ),
    ] = 5,
    include_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--descendants/--context-only",
            help=(
                "Include each selected Context root's readable lexical "
                "descendants, independently of embedded Context traversal"
            ),
        ),
    ] = None,
    follow_embeds: Annotated[
        Optional[bool],
        typer.Option(
            "--follow-embeds/--exclude-embeds",
            help=(
                "Follow embedded Context links from the selected lexical "
                "scope, independently of descendant expansion"
            ),
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Search only the selected Context roots",
        ),
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
            default=(
                ContextScopePreset.RECURSIVE
                if query is None and not scope_flags_supplied
                else ContextScopePreset.DIRECT
            ),
        )
        traversal = resolve_context_traversal(
            preset=preset,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
        )
        include_descendants = traversal.include_descendants
        follow_embeds = traversal.follow_embeds
    except (TypeError, ValueError) as error:
        _exit_error(error, code=2)
    store = MemoryStore()
    try:
        prepared = prepare_search(
            store,
            context_names=context_name,
            all_contexts=all_contexts,
            interactive=query is None,
            follow_embeds=follow_embeds,
        )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        _exit_error(error, prefix="Error")

    if not 1 <= limit <= 20:
        _exit_error(ValueError("Search limit must be between 1 and 20."))
    if query is None and not _interactive_terminal():
        _exit_error(
            ValueError(
                "QUERY is required outside a terminal. In a "
                "terminal, run 'mem search' to open the interactive search."
            )
        )
    try:
        if query is None:
            open_search_workbench(
                store,
                prepared,
                include_descendants=include_descendants,
                follow_embeds=follow_embeds,
                limit=limit,
            )
            return
        request = SearchRequest(
            query=query,
            target_names=prepared.target_names,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            limit=limit,
        )
        response = run_static_search(
            store,
            prepared.catalog,
            request,
            show_progress=not prepared.all_contexts and len(prepared.target_names) == 1,
        )
        render_search_receipt(
            response,
            target_names=prepared.target_names,
            all_readable_contexts=prepared.all_contexts,
        )
    except (
        SaveContextFromSelectionError,
        SearchError,
        QueryProviderError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        _exit_error(error)
