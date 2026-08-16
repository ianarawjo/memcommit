"""CLI bootstrap for reviewed, deterministic multi-Context Replace."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.interfaces.cli.replace import (
    render_replace_apply_result,
    render_replace_plan,
)
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
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.replace_application import (
    FrozenReplacePlan,
    ReplaceError,
    ReplaceRequest,
)
from memcommit.replace_runtime import (
    MemoryStoreReplacePort,
    execute_replace_plan,
)
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
    apply_digest: Annotated[
        Optional[str],
        typer.Option(
            "--apply",
            metavar="PLAN_DIGEST",
            help="Apply only if the newly frozen plan has this reviewed digest",
        ),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option("--plain", help="Print the plan instead of opening the TUI"),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", help="Require the interactive Replace workbench"),
    ] = False,
) -> None:
    """Preview exact replacements, then apply one reviewed atomic command."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        if delete_match and replacement is not None:
            raise ValueError("REPLACEMENT and --delete-match cannot be used together.")
        if apply_digest is not None and tui:
            raise ValueError("--apply executes the reviewed plan and cannot use --tui.")

        terminal = SystemTerminalCapabilities()
        if pattern is None and (
            mode is ConsoleMode.PLAIN
            or apply_digest is not None
            or not terminal.is_interactive()
        ):
            raise ValueError(
                "PATTERN is required outside a terminal. In a terminal, run "
                "'mem replace' to open interactive Replace."
            )
        if (
            pattern is not None
            and replacement is None
            and not delete_match
            and (
                mode is ConsoleMode.PLAIN
                or apply_digest is not None
                or not terminal.is_interactive()
            )
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

        ports: dict[int, MemoryStoreReplacePort] = {}

        def prepare(next_request: ReplaceRequest) -> FrozenReplacePlan:
            port = MemoryStoreReplacePort(store)
            from memcommit.replace_application import plan_replace

            plan = plan_replace(next_request, port=port)
            ports[id(plan)] = port
            return plan

        def apply(plan: FrozenReplacePlan):
            port = ports.pop(id(plan), None)
            if port is None:
                raise RuntimeError("Replace plan is no longer owned by this command.")
            return execute_replace_plan(plan, port=port)

        if apply_digest is not None:
            assert request is not None
            plan = prepare(request)
            if plan.plan_digest != apply_digest:
                raise ValueError(
                    "Replace plan digest does not match the reviewed plan; preview again."
                )
            typer.echo(render_replace_apply_result(apply(plan)))
            return

        if mode is ConsoleMode.TUI or (
            mode is ConsoleMode.AUTO and terminal.is_interactive()
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
                prepare=prepare,
                apply=apply,
            )
            if outcome is None:
                typer.echo("Replace closed.")
            return

        assert request is not None
        typer.echo(render_replace_plan(prepare(request)))
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
