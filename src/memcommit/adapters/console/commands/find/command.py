"""Semantic Find by default, with provider-free exact matching via --literal."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.adapters.console.clipboard import ClipboardError, write_system_clipboard
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.adapters.console.commands.find.presentation import (
    DEFAULT_FIND_PREVIEW_MATCHES,
    render_find_result,
)
from memcommit.adapters.console import SystemTerminalCapabilities
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.commands.find.workbench import (
    FindTuiSetup,
    run_find_workbench,
)
from memcommit.application.operations.find.application import (
    FindError,
    FindRequest,
    FindResult,
)
from memcommit.application.operations.find.runtime import execute_find
from memcommit.application.operations.find.save_context import (
    save_context_request_from_find,
)
from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextFromSelectionError,
)
from memcommit.application.capabilities.save_context_from_selection.runtime import (
    execute_save_context_from_selection,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


def cmd(
    query: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=(
                "Natural-language query, or exact text with --literal; omit in a "
                "terminal to open interactive Find with compact exact-Context Scope, "
                "Browse-only Profile/multiple selection, lexical range choices, and checked-result COPY Save"
            ),
        ),
    ] = None,
    literal: Annotated[
        bool,
        typer.Option(
            "--literal",
            help="Find exact text or explicit regex matches without a semantic provider",
        ),
    ] = False,
    limit: Annotated[
        Optional[int],
        typer.Option(
            "--limit",
            "-n",
            show_default=False,
            help="Maximum semantic matches (1-20; default 5); unavailable with --literal",
        ),
    ] = None,
    context_name: Annotated[
        Optional[list[str]],
        typer.Option(
            "--context",
            "-c",
            show_default=False,
            help="Readable Context root; repeat for multiple roots (defaults to current)",
        ),
    ] = None,
    include_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--descendants/--context-only",
            help="Include readable lexical descendants of each selected root",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Search only selected Context roots"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include lexical descendants",
        ),
    ] = False,
    regex: Annotated[
        bool,
        typer.Option(
            "--regex",
            help="With --literal: interpret the text as a regular expression",
        ),
    ] = False,
    ignore_case: Annotated[
        bool,
        typer.Option(
            "--ignore-case", "-i", help="With --literal: match without case sensitivity"
        ),
    ] = False,
    copy_result: Annotated[
        bool,
        typer.Option("--copy", help="With --literal: copy the complete plain result"),
    ] = False,
    all_contexts: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Search all readable Contexts in the active Profile",
        ),
    ] = False,
    show_all_results: Annotated[
        bool,
        typer.Option(
            "--all-results",
            help="With --literal: print every match instead of the bounded preview",
        ),
    ] = False,
) -> None:
    """Find relevant Memories semantically, or exact text with --literal."""

    if literal:
        if limit is not None:
            typer.secho(
                "Find error: --limit/-n is unavailable with --literal.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        _run_literal_find(
            pattern=query,
            context_name=context_name,
            include_descendants=include_descendants,
            direct=direct,
            recursive=recursive,
            regex=regex,
            ignore_case=ignore_case,
            copy_result=copy_result,
            all_contexts=all_contexts,
            show_all_results=show_all_results,
        )
        return

    if regex or ignore_case or copy_result or show_all_results:
        typer.secho(
            "Find error: --regex, --ignore-case/-i, --copy and --all-results require --literal.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    # Preserve the reviewed semantic and exact application contracts separately.
    from memcommit.adapters.console.commands.search.command import (
        cmd as run_semantic_find,
    )

    run_semantic_find(
        query=query,
        context_name=context_name,
        all_contexts=all_contexts,
        limit=5 if limit is None else limit,
        include_descendants=include_descendants,
        direct=direct,
        recursive=recursive,
    )


def _run_literal_find(
    *,
    pattern: str | None,
    context_name: list[str] | None,
    include_descendants: bool | None,
    direct: bool,
    recursive: bool,
    regex: bool,
    ignore_case: bool,
    copy_result: bool,
    all_contexts: bool,
    show_all_results: bool,
) -> None:
    """Run the existing complete exact-match path without a semantic provider."""

    try:
        traversal = resolve_context_traversal(
            preset=resolve_scope_preset(
                direct=direct,
                recursive=recursive,
                default=ContextScopePreset.DIRECT,
            ),
            include_descendants=include_descendants,
        )
        terminal = SystemTerminalCapabilities()
        if pattern is None and not terminal.is_interactive():
            raise ValueError(
                "PATTERN is required outside a terminal. In a terminal, run "
                "'mem find --literal' to open interactive Find."
            )

        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        if all_contexts and context_name:
            raise ValueError("--all/-a cannot be combined with --context/-c.")
        operands: tuple[str | None, ...] = (
            tuple(context_name) if context_name else (None,)
        )
        context_candidates = freeze_profile_context_access_candidates(
            store,
            current_name=snapshot.current_name,
        )
        accesses = tuple(
            resolve_existing_context_access(
                store,
                operand,
                current_name=snapshot.current_name,
                candidates=context_candidates,
            ).value
            for operand in operands
        )
        target_names = tuple(access.access_name for access in accesses)
        if len(set(target_names)) != len(target_names):
            raise ValueError("Find Context roots must be distinct.")
        # The TUI explicitly promises ALL READABLE CONTEXTS, so freeze the
        # Profile-wide readable namespace even when the initial root is exact.
        catalog = freeze_profile_readable_context_catalog(
            store,
            accesses[0],
        )
        if all_contexts:
            # Expand the virtual Profile target before request construction;
            # neither storage nor the application accepts PROFILE as a name.
            target_names = tuple(catalog.list_context_names())
            accesses = tuple(catalog.access_for(name) for name in target_names)
        for access in accesses:
            catalog.access_for(access.access_name)

        request = (
            None
            if pattern is None
            else FindRequest(
                pattern=pattern,
                target_names=target_names,
                include_descendants=traversal.include_descendants,
                mode="REGEX" if regex else "LITERAL",
                ignore_case=ignore_case,
            )
        )

        def execute(next_request: FindRequest) -> FindResult:
            return execute_find(next_request, catalog=catalog)

        # Missing input opens the operation's input editor. A complete request
        # always executes through the same result projection, independent of TTY.
        if request is None:
            names = tuple(catalog.list_context_names())
            current = snapshot.current_name
            current_name = current if current in names else target_names[0]
            annotations = tuple()
            outcome = run_find_workbench(
                request,
                setup=FindTuiSetup(
                    names=names,
                    current_name=current_name,
                    initial_targets=target_names,
                    annotations=annotations,
                ),
                execute=execute,
                clipboard_writer=write_system_clipboard,
                initial_all_readable_contexts=all_contexts,
                local_context_names=tuple(store.list_context_names()),
                validate_save_location=store.assert_context_creatable,
            )
            result = None if outcome is None else outcome.result
            if outcome is not None and outcome.status == "SAVE":
                assert outcome.save_as is not None
                assert outcome.save_location is not None
                saved = execute_save_context_from_selection(
                    save_context_request_from_find(
                        outcome.result,
                        outcome.selected_match_indices,
                        mode=outcome.save_as,
                        destination_name=outcome.save_location,
                        catalog=catalog,
                    ),
                    store=store,
                    catalog=catalog,
                )
                typer.secho(
                    f"Saved {len(saved.item_uids)} checked Find match(es) as "
                    f"{saved.mode} in new Context "
                    f"'{display_escape_text(saved.context_name)}' "
                    f"[{saved.context_uid[:8]}]; sources unchanged.",
                    fg=typer.colors.GREEN,
                )
        else:
            assert request is not None
            result = execute(request)
            typer.echo(
                render_find_result(
                    result,
                    match_limit=(
                        None if show_all_results else DEFAULT_FIND_PREVIEW_MATCHES
                    ),
                    all_readable_contexts=all_contexts,
                )
            )

        if result is None:
            typer.echo("Find closed.")
            return
        if copy_result:
            result_uses_all_readable_contexts = (
                all_contexts
                and result.request.target_names == tuple(catalog.list_context_names())
            )
            write_system_clipboard(
                render_find_result(
                    result,
                    all_readable_contexts=result_uses_all_readable_contexts,
                )
            )
            typer.secho("Copied complete Find result.", fg=typer.colors.GREEN, err=True)
    except (
        ClipboardError,
        FileNotFoundError,
        FindError,
        OSError,
        ProfileConfigError,
        ProfileError,
        SaveContextFromSelectionError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Find error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


__all__ = ["cmd"]
