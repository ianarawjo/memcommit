"""Generate bounded, explicitly unverified Rule or Case proposals."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.bootstrap import build_elaborate_console_runner
from memcommit.clipboard import write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.elaborate import ElaborateError
from memcommit.elaborate_application import ElaborateRequest, ElaborateResult
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.ground_elaborate import (
    FrozenGroundElaborate,
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.interfaces.console import (
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
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
            "-r",
            help=(
                "Rule to elaborate into suggested Case propositions; repeat for "
                "more Rules"
            ),
        ),
    ] = None,
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
    """Elaborate a Goal into candidate Rules or Rules into concrete Cases."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        frozen_ground: FrozenGroundElaborate | None = None
        ground_store: MemoryStore | None = None
        if ground is None:
            if from_goal or from_rules:
                raise ElaborateError("--from-goal/--from-rules require --ground.")
            request = ElaborateRequest(goal=goal, rules=tuple(rule or ()))
        else:
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

        def execute(value: ElaborateRequest) -> ElaborateResult:
            with CommandProgress(
                "ELABORATE",
                "generating review proposals",
                total=1,
            ) as progress:
                result = (
                    execute_elaborate(
                        value,
                        provider_factory=connect_semantic_provider,
                    )
                    if frozen_ground is None or ground_store is None
                    else execute_ground_elaborate(
                        frozen_ground,
                        store=ground_store,
                        provider_factory=connect_semantic_provider,
                    ).elaborate
                )
                progress.update("proposal ready", step=1)
                return result

        runner = build_elaborate_console_runner(
            execute=execute,
            clipboard_writer=write_system_clipboard,
            terminal=SystemTerminalCapabilities(),
        )
        runner.run(request, mode=mode)
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
