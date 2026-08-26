"""CLI bootstrap for direct, deterministic multi-Context Replace."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.infrastructure.command_ledger.attempts import annotate_command_outcome
from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.interfaces.cli.replace import render_replace_apply_result
from memcommit.interfaces.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.replace import (
    ReplaceTuiSetup,
    run_replace_tui,
)
from memcommit.operations.profile.config import ProfileConfigError
from memcommit.operations.profile.model import ProfileError
from memcommit.operations.replace.application import ReplaceError, ReplaceRequest
from memcommit.operations.replace.runtime import execute_replace_with_store
from memcommit.store import MemoryStore


def cmd(
    pattern: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help="Exact text pattern; omit in a terminal to open Replace",
        ),
    ] = None,
    replacement: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help="Literal replacement text; use --delete-match for an empty value",
        ),
    ] = None,
    context_name: Annotated[
        Optional[list[str]],
        typer.Option(
            "--context",
            "-c",
            show_default=False,
            help="Ordinary local Context root; repeat for multiple roots",
        ),
    ] = None,
    include_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--descendants/--context-only",
            help="Include lexical descendants of each selected root",
        ),
    ] = None,
    follow_embeds: Annotated[
        Optional[bool],
        typer.Option(
            "--follow-embeds/--exclude-embeds",
            help="Follow embedded local Context owners independently",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Use only selected Context roots"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include lexical descendants and embedded Context owners",
        ),
    ] = False,
    regex: Annotated[
        bool,
        typer.Option(
            "--regex",
            help="Interpret PATTERN as a regular expression; replacement stays literal",
        ),
    ] = False,
    ignore_case: Annotated[
        bool,
        typer.Option("--ignore-case", "-i", help="Match without case sensitivity"),
    ] = False,
    delete_match: Annotated[
        bool,
        typer.Option(
            "--delete-match",
            help="Replace each match with empty text",
        ),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option("--plain", help="Print an ANSI-free execution receipt"),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", help="Edit the request in compact interactive Replace"),
    ] = False,
) -> None:
    """Replace exact matches immediately as one atomic Undoable command."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        if delete_match and replacement is not None:
            raise ValueError("REPLACEMENT and --delete-match cannot be used together.")

        terminal = SystemTerminalCapabilities()
        if pattern is None and (
            mode is ConsoleMode.PLAIN or not terminal.is_interactive()
        ):
            raise ValueError(
                "PATTERN is required outside a terminal. In a terminal, run "
                "'mem replace' to open interactive Replace."
            )
        if (
            pattern is not None
            and replacement is None
            and not delete_match
            and (mode is ConsoleMode.PLAIN or not terminal.is_interactive())
        ):
            raise ValueError(
                "REPLACEMENT or --delete-match is required outside the TUI."
            )

        traversal = resolve_context_traversal(
            preset=resolve_scope_preset(
                direct=direct,
                recursive=recursive,
                default=ContextScopePreset.DIRECT,
            ),
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
        )
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        operands: tuple[str | None, ...] = (
            tuple(context_name) if context_name else (None,)
        )
        target_names = tuple(snapshot.resolve_or_current(value) for value in operands)
        if any(name is None for name in target_names):
            raise FileNotFoundError("No current Context is available.")
        canonical_targets = tuple(name for name in target_names if name is not None)
        if len(set(canonical_targets)) != len(canonical_targets):
            raise ValueError("Replace Context roots must be distinct.")
        if any(not store.context_exists(name) for name in canonical_targets):
            raise FileNotFoundError(
                "Replace targets must be ordinary local Contexts in this Store."
            )

        request = (
            None
            if pattern is None
            else ReplaceRequest(
                pattern=pattern,
                replacement="" if delete_match or replacement is None else replacement,
                target_names=canonical_targets,
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
                mode="REGEX" if regex else "LITERAL",
                ignore_case=ignore_case,
            )
        )

        def execute(next_request: ReplaceRequest):
            return execute_replace_with_store(next_request, store=store)

        if mode is ConsoleMode.TUI or (
            mode is ConsoleMode.AUTO
            and terminal.is_interactive()
            and (pattern is None or (replacement is None and not delete_match))
        ):
            names = tuple(store.list_context_names())
            current = snapshot.current_name
            current_name = current if current in names else canonical_targets[0]
            outcome = run_replace_tui(
                request,
                setup=ReplaceTuiSetup(
                    names=names,
                    current_name=current_name,
                    initial_targets=canonical_targets,
                ),
                execute=execute,
            )
            if outcome is None:
                annotate_command_outcome("CANCELLED")
                typer.echo("Replace closed.")
            else:
                if not outcome.applied:
                    annotate_command_outcome("NO_CHANGE")
                typer.echo(render_replace_apply_result(outcome))
            return

        assert request is not None
        result = execute(request)
        if not result.applied:
            annotate_command_outcome("NO_CHANGE")
        typer.echo(render_replace_apply_result(result))
    except (
        ConsoleModeError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        ReplaceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Replace error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


__all__ = ["cmd"]
