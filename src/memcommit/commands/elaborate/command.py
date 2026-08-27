"""Generate exact-count, explicitly unverified Rule or Case proposals."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.bootstrap import build_elaborate_console_runner
from memcommit.infrastructure.clipboard import write_system_clipboard
from memcommit.commands.shared.command_progress import CommandProgress
from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.application.operations.elaborate.model import ElaborateError, ElaborateMode
from memcommit.application.operations.elaborate.application import ElaborateRequest, ElaborateResult
from memcommit.semantic.goal_focus_runtime import freeze_goal_focus_operand
from memcommit.application.operations.elaborate.add_runtime import (
    FrozenElaborateSource,
    PreparedElaborateAdd,
    apply_prepared_elaborate_add,
    freeze_elaborate_context_source,
    prepare_elaborate_add,
)
from memcommit.application.operations.ground.elaborate import (
    FrozenGroundElaborate,
    GroundElaborateResult,
    apply_ground_elaborate_result,
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.adapters.interfaces.cli.semantic_add import render_applied_memory_preview
from memcommit.adapters.interfaces.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.infrastructure.providers.subscription import QueryProviderError, connect_semantic_provider
from memcommit.application.operations.add.semantic_runtime import (
    resolve_semantic_add_endpoints,
    resolve_semantic_add_target,
)
from memcommit.persistence.store import MemoryStore


def cmd(
    goal: Annotated[
        Optional[str],
        typer.Option(
            "--goal",
            "-g",
            help=(
                "Goal focus as a Context, CONTEXT:UID/UID Memory, or inline "
                "text; alone it is also the Goal Source for Rule generation"
            ),
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
    number: Annotated[
        Optional[int],
        typer.Option(
            "--number",
            "--n",
            "-n",
            min=1,
            help="Exact positive proposal count (default 3; no fixed maximum)",
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help=(
                "Require generated Cases to pass independent Source Rule "
                "Conformance and Fit before Add"
            ),
        ),
    ] = False,
    ground: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help="Use one exact saved Ground revision instead of inline input",
        ),
    ] = None,
    adopt: Annotated[
        bool,
        typer.Option(
            "--adopt",
            help=(
                "Explicitly add the complete physical-Ground proposal to its "
                "/rules or /examples lane"
            ),
        ),
    ] = False,
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
        typer.Option("--plain", help="Print a read-only Ground result without a Viewer"),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", help="Require the read-only Ground result Viewer"),
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
        if adopt and tui:
            raise ElaborateError(
                "--adopt cannot use the read-only TUI; the explicit "
                "line-oriented command is the adoption boundary."
            )
        frozen_ground: FrozenGroundElaborate | None = None
        ground_result: GroundElaborateResult | None = None
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
                number=number,
                strict=strict,
            )
            request = frozen_ground.request
        else:
            if adopt:
                raise ElaborateError("--adopt requires --ground.")
            if from_goal or from_rules:
                raise ElaborateError("--from-goal/--from-rules require --ground.")
            ordinary_store = MemoryStore(create=False)
            snapshot = ContextOperandSnapshot.capture(ordinary_store)
            goal_focus = (
                freeze_goal_focus_operand(
                    ordinary_store,
                    goal,
                    current_name=snapshot.current_name,
                )
                if goal is not None
                else None
            )
            inline_rules = bool(rule)
            if source_name is not None and inline_rules:
                raise ElaborateError(
                    "Inline --rule input cannot be combined with --from."
                )
            context_source = source_name is not None or (
                not inline_rules and goal_focus is None
            )
            if not context_source:
                if as_role != "rules":
                    raise ElaborateError("--as applies only to a Context Source.")
                if inline_rules:
                    request = ElaborateRequest(
                        rules=tuple(rule or ()),
                        goal_focus=goal_focus,
                        number=number,
                        strict=strict,
                    )
                else:
                    assert goal_focus is not None
                    if len(goal_focus.items) != 1:
                        raise ElaborateError(
                            "Standalone --goal requires one Goal item; use --from "
                            "with --as goal for an exact one-Memory Goal Source."
                        )
                    request = ElaborateRequest(
                        goal=goal_focus.text,
                        goal_focus=goal_focus,
                        number=number,
                        strict=strict,
                    )
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
                    number=number,
                    strict=strict,
                    goal_focus=goal_focus,
                )
                request = ordinary_source.request
                ordinary_target = endpoints.target_name

        def execute(value: ElaborateRequest) -> ElaborateResult:
            nonlocal prepared, ground_result
            with CommandProgress(
                "ELABORATE",
                "generating review proposals",
                total=1,
            ) as progress:
                if frozen_ground is not None and ground_store is not None:
                    ground_result = execute_ground_elaborate(
                        frozen_ground,
                        store=ground_store,
                        provider_factory=connect_semantic_provider,
                    )
                    result = ground_result.elaborate
                else:
                    assert ordinary_store is not None
                    assert ordinary_target is not None
                    prepared = prepare_elaborate_add(
                        store=ordinary_store,
                        request=value,
                        target_name=ordinary_target,
                        provider_factory=connect_semantic_provider,
                        source=ordinary_source,
                        will_apply=True,
                    )
                    result = prepared.result
                progress.update("proposal ready", step=1)
                return result

        runner = build_elaborate_console_runner(
            execute=execute,
            clipboard_writer=write_system_clipboard,
            terminal=SystemTerminalCapabilities(),
        )
        if frozen_ground is None:
            if tui:
                raise ElaborateError(
                    "Direct Elaborate Add is non-interactive; use "
                    "'mem impact elaborate' to inspect without saving."
                )
            result = execute(request)
        else:
            result = runner.run(request, mode=mode)
        if frozen_ground is not None:
            if adopt:
                if ground_result is None or ground_store is None:
                    raise ElaborateError("Elaborate produced no Ground proposal.")
                receipt = apply_ground_elaborate_result(
                    ground_result,
                    store=ground_store,
                )
                typer.secho(
                    f"ELABORATE ADOPTED · {display_escape_text(receipt.workspace_name)}"
                    f"/{receipt.lane}",
                    fg=typer.colors.GREEN,
                    bold=True,
                )
                typer.echo(
                    f"EFFECTS · ADD {len(receipt.memory_uids)} MEMORIES · "
                    f"GROUND REVISION {receipt.revision}"
                )
                typer.echo(f"UNDO · mem ground {receipt.workspace_name} --undo")
            return
        if result is None or prepared is None or ordinary_store is None:
            raise ElaborateError("Elaborate produced no addable proposal.")
        receipt = apply_prepared_elaborate_add(prepared, store=ordinary_store)
        typer.secho(
            f"ELABORATE APPLIED · {display_escape_text(receipt.target_name)}",
            fg=typer.colors.GREEN,
            bold=True,
        )
        source_label = receipt.source_name or "INLINE"
        typer.echo(
            f"MODE · {prepared.result.analysis.mode.value} · "
            "VERIFICATION · UNVERIFIED · "
            f"QUALITY · {prepared.result.analysis.quality_policy.value}"
        )
        typer.echo(
            f"SOURCE · {display_escape_text(source_label)} · "
            f"TARGET · {display_escape_text(receipt.target_name)}"
        )
        typer.echo(f"EFFECTS · ADD {receipt.count} MEMORIES")
        analysis = prepared.result.analysis
        added_contents = (
            tuple(item.content for item in analysis.rules)
            if analysis.mode is ElaborateMode.GOAL_TO_RULES
            else tuple(item.proposition for item in analysis.cases)
        )
        render_applied_memory_preview(receipt.memory_uids, added_contents)
        typer.echo(f"REVIEW · mem review elaborate --receipt {receipt.checkpoint_uid}")
        typer.echo("UNDO · mem undo")
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
