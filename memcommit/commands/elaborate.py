"""Generate bounded, explicitly unverified Rule or Case proposals."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.bootstrap import build_elaborate_console_runner
from memcommit.clipboard import write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.elaborate import ElaborateError
from memcommit.elaborate_application import ElaborateRequest, ElaborateResult
from memcommit.elaborate_add_runtime import (
    FrozenElaborateSource,
    PreparedElaborateAdd,
    apply_prepared_elaborate_add,
    freeze_elaborate_context_source,
    prepare_elaborate_add,
)
from memcommit.ground_elaborate import (
    FrozenGroundElaborate,
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.interfaces.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.semantic_add_runtime import (
    resolve_semantic_add_endpoints,
    resolve_semantic_add_target,
)
from memcommit.store import MemoryStore


def cmd(
    goal: Annotated[
        Optional[str],
        typer.Option(
            "--goal",
            "-g",
            help="Goal to elaborate into suggested, unverified Rules",
        ),
    ] = None,
    rule: Annotated[
        Optional[list[str]],
        typer.Option(
            "--rule",
            help=(
                "Rule to elaborate into suggested Case propositions; repeat for "
                "more Rules"
            ),
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Existing Source Context (defaults to current)",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Existing Context that receives generated Memories (defaults to current)",
        ),
    ] = None,
    as_role: Annotated[
        str,
        typer.Option(
            "--as",
            help="Interpret Context Source Memories as rules (default) or one goal",
        ),
    ] = "rules",
    ground: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help="Use one exact saved Ground revision instead of inline input",
        ),
    ] = None,
    from_goal: Annotated[
        bool,
        typer.Option(
            "--from-goal",
            help="With --ground, propose Rules from its Goal",
        ),
    ] = False,
    from_rules: Annotated[
        bool,
        typer.Option(
            "--from-rules",
            help=(
                "With --ground, propose Case propositions from its active Rules"
            ),
        ),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option("--plain", help="Print proposals instead of opening the Viewer"),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", help="Require the interactive proposal Viewer"),
    ] = False,
) -> None:
    """Generate Rules or Cases and add them to an existing Context."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        # Standalone semantic Add commands are line-oriented by default. Impact
        # owns non-mutating inspection, so a TTY must not silently change the
        # command into an interactive preview workflow.
        if mode is ConsoleMode.AUTO:
            mode = ConsoleMode.PLAIN
        frozen_ground: FrozenGroundElaborate | None = None
        ground_store: MemoryStore | None = None
        prepared: PreparedElaborateAdd | None = None
        ordinary_store: MemoryStore | None = None
        ordinary_source: FrozenElaborateSource | None = None
        ordinary_target: str | None = None
        if ground is not None:
            if source_name is not None or target_name is not None or as_role != "rules":
                raise ElaborateError(
                    "--ground cannot be combined with --from, --to, or --as."
                )
            if goal is not None or rule:
                raise ElaborateError(
                    "Use --ground or inline --goal/--rule input, not both."
                )
            if from_goal == from_rules:
                raise ElaborateError(
                    "With --ground, choose exactly one of --from-goal or --from-rules."
                )
            ground_store = MemoryStore(create=False)
            frozen_ground = freeze_ground_elaborate(
                ground_store,
                ground_name=ground,
                direction="GOAL_TO_RULES" if from_goal else "RULES_TO_CASES",
            )
            request = frozen_ground.request
        else:
            if from_goal or from_rules:
                raise ElaborateError("--from-goal/--from-rules require --ground.")
            ordinary_store = MemoryStore(create=False)
            snapshot = ContextOperandSnapshot.capture(ordinary_store)
            inline = goal is not None or bool(rule)
            if inline:
                if source_name is not None:
                    raise ElaborateError(
                        "Inline --goal/--rule input cannot be combined with --from."
                    )
                if as_role != "rules":
                    raise ElaborateError("--as applies only to a Context Source.")
                request = ElaborateRequest(goal=goal, rules=tuple(rule or ()))
                ordinary_target = resolve_semantic_add_target(
                    target_locator=target_name,
                    current=snapshot.current_name,
                )
            else:
                endpoints = resolve_semantic_add_endpoints(
                    source_locator=source_name,
                    target_locator=target_name,
                    current=snapshot.current_name,
                )
                if as_role not in {"goal", "rules"}:
                    raise ElaborateError("Elaborate --as must be 'goal' or 'rules'.")
                ordinary_source = freeze_elaborate_context_source(
                    ordinary_store,
                    context_name=endpoints.source_name,
                    role=as_role,
                )
                request = ordinary_source.request
                ordinary_target = endpoints.target_name

        def execute(value: ElaborateRequest) -> ElaborateResult:
            nonlocal prepared
            with CommandProgress(
                "ELABORATE",
                "generating review proposals",
                total=1,
            ) as progress:
                if frozen_ground is not None and ground_store is not None:
                    result = execute_ground_elaborate(
                        frozen_ground,
                        store=ground_store,
                        provider_factory=connect_semantic_provider,
                    ).elaborate
                else:
                    assert ordinary_store is not None
                    assert ordinary_target is not None
                    prepared = prepare_elaborate_add(
                        store=ordinary_store,
                        request=value,
                        target_name=ordinary_target,
                        provider_factory=connect_semantic_provider,
                        source=ordinary_source,
                    )
                    result = prepared.result
                progress.update("proposal ready", step=1)
                return result

        runner = build_elaborate_console_runner(
            execute=execute,
            clipboard_writer=write_system_clipboard,
            terminal=SystemTerminalCapabilities(),
        )
        result = runner.run(request, mode=mode)
        if frozen_ground is not None:
            # Ground remains an exact read-only proposal adapter until its
            # workspace source locks can participate in the same atomic Add.
            return
        if result is None or prepared is None or ordinary_store is None:
            raise ElaborateError("Elaborate produced no addable proposal.")
        receipt = apply_prepared_elaborate_add(prepared, store=ordinary_store)
        typer.echo("")
        typer.secho(
            f"Added {receipt.count} Elaborate Memories to "
            f"'{display_escape_text(receipt.target_name)}'.",
            fg=typer.colors.GREEN,
        )
        source_label = receipt.source_name or "INLINE"
        typer.echo(
            f"SOURCE · {display_escape_text(source_label)} · TARGET · "
            f"{display_escape_text(receipt.target_name)}"
        )
        typer.echo(
            f"CHECKPOINT · {receipt.checkpoint_uid[:8]} · RECOVERY · mem undo"
        )
    except (
        ConsoleModeError,
        ElaborateError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Elaborate error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
