import shlex
import sys
from collections.abc import Sequence
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.adapters.console.commands.search.search_workbench import (
    run_search_workbench,
)
from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextFromSelectionError,
)
from memcommit.application.capabilities.save_context_from_selection.runtime import (
    execute_save_context_from_selection,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.application.capabilities.authority.readable_contexts import (
    ReadableContextCatalog,
    freeze_readable_context_catalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.commands.search.result_present import group_search_items
from memcommit.core.context import Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.search.application import (
    SearchRequest,
    SearchResponse,
    SearchStage,
)
from memcommit.application.operations.search.runtime import execute_search
from memcommit.application.operations.search.save_context import (
    save_context_request_from_search,
)
from memcommit.providers.operation_connections import connect_search_provider
from memcommit.providers.subscription import QueryProviderError
from memcommit.application.operations.search.model import (
    SearchError,
    SearchArtifact,
    SearchMatch,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceState,
)
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_object_label,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _render_labeled_content(label: str, content: str) -> None:
    """Render the first content line beside its item and align continuations."""
    lines = safe_terminal_text(content).splitlines() or [""]
    typer.echo(f"{label} {lines[0]}")
    continuation = " " * (len(label) + 1)
    for line in lines[1:]:
        typer.echo(f"{continuation}{line}")


def _render_match(match: SearchMatch) -> None:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        item_label = source_object_label(SourceForm.MEMORY)
        relevance = " · RELATED" if match.relevance == "related" else ""
        _render_labeled_content(
            f"[{item_label} {item.uid[:8]}]{relevance}",
            item.content,
        )
    elif isinstance(item, MemoryRef):
        facts = SourceDisplayFacts(
            form=SourceForm.MEMORY_REF,
            states=(
                (SourceState.READ_ONLY,)
                if item.target is not None
                else (SourceState.DANGLING,)
            ),
        )
        item_label = source_object_label(facts)
        annotations = [
            *(("RELATED",) if match.relevance == "related" else ()),
            source_annotation_text(facts),
        ]
        annotation = " · ".join(value for value in annotations if value)
        label = (
            f"[{item_label} {item.uid[:8]}]"
            + (f" · {annotation}" if annotation else "")
            + " "
            + f"-> {display_escape_text(item.target_context_name)}#"
            f"{display_escape_text(item.target_memory_uid[:8])}"
        )
        if item.target is not None:
            _render_labeled_content(label, item.target.content)
        else:
            typer.echo(label)
    elif isinstance(item, QueryContextRef):
        item_label = source_object_label(SourceForm.QUERY_VIEW)
        relevance = " · RELATED" if match.relevance == "related" else ""
        label = f"[{item_label} {item.uid[:8]}]{relevance}"
        typer.echo(f"{label} {display_escape_text(item.name)}")
        command = shlex.join(
            [
                "mem",
                "query",
                item.name,
                "<question>",
                "--context",
                candidate.context_name,
            ]
        )
        typer.echo(f"{' ' * (len(label) + 1)}Ask with: {display_escape_text(command)}")
    elif isinstance(item, SearchArtifact):
        label = (
            f"[related {item.artifact_kind} {item.uid[:8]}]"
            if match.relevance == "related"
            else f"[{item.artifact_kind} {item.uid[:8]}]"
        )
        summary = item.summary.strip() or item.title
        _render_labeled_content(label, f"{item.title} · {summary}")


def _run_search_request(
    store: MemoryStore,
    catalog: ReadableContextCatalog,
    request: SearchRequest,
    *,
    observer=None,
) -> SearchResponse:
    """Compatibility adapter over the terminal-independent Search runtime."""

    return execute_search(
        request,
        store=store,
        catalog=catalog,
        provider_factory=connect_search_provider,
        observer=observer,
    )


def _render_search_response(
    response: SearchResponse,
    *,
    target_names: tuple[str, ...],
    all_readable_contexts: bool = False,
) -> None:
    """Present one typed application result without rerunning its search."""

    heading = (
        "ALL READABLE CONTEXTS"
        if all_readable_contexts
        else " + ".join(display_escape_text(name) for name in target_names)
    )
    if not response.results:
        typer.secho(heading, bold=True)
        typer.echo("  (no matching items)")
        return
    if response.related_query:
        if len(target_names) == 1:
            typer.secho(heading, bold=True)
            typer.echo("  (no primary matches)")
            typer.echo()
        typer.secho("RELATED RESULTS", bold=True)
        typer.echo(
            "  No matching results for: " + display_escape_text(response.request.query)
        )
        typer.echo("  Broader search: " + display_escape_text(response.related_query))
        typer.echo()
    groups = group_search_items(
        response.results,
        context_name=lambda result: result.context_name,
    )
    for group_index, (owner_name, results) in enumerate(groups):
        if group_index or response.related_query:
            typer.echo()
        typer.secho(display_escape_text(owner_name), bold=True)
        for result in results:
            if result.current_match is not None:
                _render_match(result.current_match)
                continue
            related = " · RELATED" if result.relevance == "related" else ""
            _render_labeled_content(
                f"[{result.kind} {result.uid[:8]}]{related}",
                result.content,
            )
    if response.related_query:
        typer.echo()
        typer.echo("Related results may not satisfy the original query.")


def _open_search_workbench(
    store: MemoryStore,
    access: ContextAccess,
    *,
    current_name: str | None,
    initial_targets: Sequence[str] = (),
    include_descendants: bool,
    follow_embeds: bool,
    limit: int,
) -> None:
    """Open a blank, query-focused Search over one frozen readable catalog."""

    catalog = freeze_profile_readable_context_catalog(
        store,
        access,
        include_query_routes=True,
    )
    names = tuple(catalog.list_context_names())
    initial_target = access.display_name
    if initial_target not in names:
        raise RuntimeError("The selected Context is outside the readable catalog.")
    displayed_current = current_name if current_name in names else initial_target
    granted_names = frozenset(
        name for name in names if catalog.access_for(name).is_granted
    )
    annotations = {
        name: context_access_display_facts(catalog.access_for(name))
        for name in granted_names
    }
    workbench_result = run_search_workbench(
        names,
        current=displayed_current,
        initial_target=initial_target,
        initial_targets=initial_targets or (initial_target,),
        initial_include_descendants=include_descendants,
        initial_follow_embeds=follow_embeds,
        limit=limit,
        run_search=lambda request: _run_search_request(
            store,
            catalog,
            request,
        ),
        annotations=annotations,
        local_context_names=tuple(store.list_context_names()),
        validate_save_location=store.assert_context_creatable,
    )
    # Compatibility capture stubs used by read-only callers historically
    # returned None; only the typed SAVE result crosses the write edge.
    if workbench_result is None or workbench_result.status != "SAVE":
        return
    assert workbench_result.response is not None
    assert workbench_result.save_as is not None
    assert workbench_result.save_location is not None
    saved = execute_save_context_from_selection(
        save_context_request_from_search(
            workbench_result.response,
            workbench_result.selected_result_indices,
            mode=workbench_result.save_as,
            destination_name=workbench_result.save_location,
            catalog=catalog,
        ),
        store=store,
        catalog=catalog,
    )
    typer.secho(
        f"Saved {len(saved.item_uids)} checked Search result(s) as "
        f"{saved.mode} in new Context "
        f"'{display_escape_text(saved.context_name)}' "
        f"[{saved.context_uid[:8]}]; sources unchanged.",
        fg=typer.colors.GREEN,
    )


def cmd(
    query: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=(
                "Natural-language query; omit in a terminal to open the "
                "interactive search with compact exact-Context Scope, "
                "Browse-only Profile/multiple selection, independent range "
                "and Embed choices, and checked-result COPY/REFERENCE/EMBED Save As"
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
        typer.secho(
            f"Search error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore()
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        if all_contexts and context_name:
            raise ValueError("--all/-a cannot be combined with --context/-c.")
        operands: tuple[str | None, ...] = (
            (context_name,)
            if isinstance(context_name, str)
            else tuple(context_name)
            if context_name
            else (None,)
        )
        accesses = tuple(
            resolve_context_access(
                store,
                operand,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            )
            for operand in operands
        )
        target_names = tuple(access.display_name for access in accesses)
        if len(set(target_names)) != len(target_names):
            raise ValueError("Search Context roots must be distinct.")
        access = accesses[0]
        all_readable_catalog = None
        if all_contexts:
            # PROFILE is a process-local shortcut, never a storage locator.
            # Freeze its concrete names once so later scope and provider work
            # cannot reinterpret --all after current/Profile state changes.
            all_readable_catalog = freeze_profile_readable_context_catalog(
                store,
                access,
                include_query_routes=follow_embeds,
            )
            target_names = tuple(all_readable_catalog.list_context_names())
            accesses = tuple(
                all_readable_catalog.access_for(name) for name in target_names
            )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if not 1 <= limit <= 20:
        typer.secho(
            "Search error: Search limit must be between 1 and 20.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if query is None:
        if not _interactive_terminal():
            typer.secho(
                "Search error: QUERY is required outside a terminal. In a "
                "terminal, run 'mem search' to open the interactive search.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            workbench_options = {
                "current_name": context_snapshot.current_name,
                "include_descendants": include_descendants,
                "follow_embeds": follow_embeds,
                "limit": limit,
            }
            if len(target_names) > 1:
                workbench_options["initial_targets"] = target_names
            _open_search_workbench(store, access, **workbench_options)
        except (
            SaveContextFromSelectionError,
            SearchError,
            QueryProviderError,
            FileNotFoundError,
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Search error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return

    request = SearchRequest(
        query=query,
        target_names=target_names,
        include_descendants=include_descendants,
        follow_embeds=follow_embeds,
        limit=limit,
    )
    try:
        if all_readable_catalog is not None or len(target_names) > 1:
            catalog = all_readable_catalog
            if catalog is None:
                catalog = freeze_profile_readable_context_catalog(
                    store,
                    access,
                    include_query_routes=follow_embeds,
                )
            for target_access in accesses:
                catalog.access_for(target_access.display_name)
            response = _run_search_request(store, catalog, request)
        else:
            catalog = freeze_readable_context_catalog(
                store,
                access,
                include_query_routes=follow_embeds,
            )
            with CommandProgress(
                "SEARCH",
                "connecting provider",
                total=3,
            ) as progress:

                def observe(stage: SearchStage) -> None:
                    if stage == "SEARCHING":
                        progress.update("ranking candidates", step=2)
                    elif stage == "CHECKING_COVERAGE":
                        progress.update("checking namespace coverage", step=3)

                response = _run_search_request(
                    store,
                    catalog,
                    request,
                    observer=observe,
                )
        _render_search_response(
            response,
            target_names=target_names,
            all_readable_contexts=all_contexts,
        )
    except (
        SearchError,
        QueryProviderError,
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Search error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
