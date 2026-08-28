"""CLI bootstrap for provider-free literal or explicit-regex Find."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.application.capabilities.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.adapters.console.clipboard import ClipboardError, write_system_clipboard
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.core.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.core.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.adapters.console.commands.find.presentation import (
    DEFAULT_FIND_PREVIEW_MATCHES,
    render_find_result,
)
from memcommit.adapters.console.commands.find.compact import run_compact_find_result
from memcommit.adapters.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
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
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


def cmd(
    pattern: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=("Exact text pattern; omit in a terminal to open interactive Find"),
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
    follow_embeds: Annotated[
        Optional[bool],
        typer.Option(
            "--follow-embeds/--exclude-embeds",
            help="Follow embedded Contexts independently of lexical descendants",
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
            help="Include lexical descendants and follow embedded Contexts",
        ),
    ] = False,
    regex: Annotated[
        bool,
        typer.Option(
            "--regex",
            help="Interpret PATTERN as a regular expression instead of literal text",
        ),
    ] = False,
    ignore_case: Annotated[
        bool,
        typer.Option("--ignore-case", "-i", help="Match without case sensitivity"),
    ] = False,
    copy_result: Annotated[
        bool,
        typer.Option("--copy", help="Copy the complete plain result after execution"),
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
            help="Print every matching row instead of the bounded preview",
        ),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print the result (the default when PATTERN is supplied)",
        ),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", help="Require the compact interactive Find form"),
    ] = False,
) -> None:
    """Find exact text spans without a provider, cache, session, or mutation."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        traversal = resolve_context_traversal(
            preset=resolve_scope_preset(
                direct=direct,
                recursive=recursive,
                default=ContextScopePreset.DIRECT,
            ),
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
        )
        terminal = SystemTerminalCapabilities()
        if pattern is None and (
            mode is ConsoleMode.PLAIN or not terminal.is_interactive()
        ):
            raise ValueError(
                "PATTERN is required outside a terminal. In a terminal, run "
                "'mem find' to open interactive Find."
            )

        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        if all_contexts and context_name:
            raise ValueError("--all/-a cannot be combined with --context/-c.")
        operands: tuple[str | None, ...] = (
            tuple(context_name) if context_name else (None,)
        )
        accesses = tuple(
            resolve_context_access(
                store,
                operand,
                current_name=snapshot.current_name,
                required_permission="READ",
            )
            for operand in operands
        )
        target_names = tuple(access.display_name for access in accesses)
        if len(set(target_names)) != len(target_names):
            raise ValueError("Find Context roots must be distinct.")
        # The TUI explicitly promises ALL READABLE CONTEXTS, so freeze the
        # Profile-wide readable namespace even when the initial root is exact.
        catalog = freeze_profile_readable_context_catalog(
            store,
            accesses[0],
            include_query_routes=False,
        )
        if all_contexts:
            # Expand the virtual Profile target before request construction;
            # neither storage nor the application accepts PROFILE as a name.
            target_names = tuple(catalog.list_context_names())
            accesses = tuple(catalog.access_for(name) for name in target_names)
        for access in accesses:
            catalog.access_for(access.display_name)

        request = (
            None
            if pattern is None
            else FindRequest(
                pattern=pattern,
                target_names=target_names,
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
                mode="REGEX" if regex else "LITERAL",
                ignore_case=ignore_case,
            )
        )

        def execute(next_request: FindRequest) -> FindResult:
            return execute_find(next_request, catalog=catalog)

        # A supplied pattern is already an executable request, so never send it
        # through full-screen setup implicitly. Short/static results stay
        # inline; a longer AUTO TTY result may use only the compact pager below.
        # --tui remains the explicit escape hatch for reviewing setup controls.
        if mode is ConsoleMode.TUI or (
            mode is ConsoleMode.AUTO and request is None and terminal.is_interactive()
        ):
            names = tuple(catalog.list_context_names())
            current = snapshot.current_name
            current_name = current if current in names else target_names[0]
            annotations = tuple(
                (name, context_access_display_facts(access))
                for name in names
                if (access := catalog.access_for(name)).is_granted
            )
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
            )
            result = None if outcome is None else outcome.result
        else:
            assert request is not None
            result = execute(request)
            if (
                mode is ConsoleMode.AUTO
                and terminal.is_interactive()
                and not show_all_results
                and len(result.matches) > DEFAULT_FIND_PREVIEW_MATCHES
            ):
                # A completed one-shot request stays in the primary terminal
                # flow. Only its bounded rows become interactive; setup and
                # result semantics remain outside the shared pager shell.
                run_compact_find_result(
                    result,
                    all_readable_contexts=all_contexts,
                )
            else:
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
        ConsoleModeError,
        FileNotFoundError,
        FindError,
        OSError,
        ProfileConfigError,
        ProfileError,
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
