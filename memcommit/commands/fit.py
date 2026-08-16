"""Judge proposition compatibility or inspect the explicit Ground adapter."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.bootstrap import (
    build_fit_console_runner,
    build_proposition_fit_console_runner,
)
from memcommit.clipboard import write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.fit import FitError, FitReport
from memcommit.fit_application import (
    FitPropositionsRequest,
    FitRequest,
    FitResult,
)
from memcommit.fit_judgment import FitJudgmentError, FitProposition
from memcommit.fit_runtime import run_fit_with_store, run_proposition_fit
from memcommit.interfaces.console import (
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.fit import fit_result_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.store import MemoryStore


def render_fit(report: FitReport, *, current: bool = True) -> str:
    """Compatibility projection for callers of the former command renderer."""

    return fit_result_text(FitResult(report, current))


def cmd(
    propositions: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Two or more complete proposition texts judged together"
        ),
    ] = None,
    background: Annotated[
        Optional[list[str]],
        typer.Option(
            "--background",
            help="Repeatable frozen background proposition used as Context K",
        ),
    ] = None,
    ground_name: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help=(
                "Check one revision-bound Ground across Context, Goal, Rules, "
                "and Examples"
            ),
        ),
    ] = None,
    receipt: Annotated[
        Optional[str],
        typer.Option(
            "--receipt",
            help="Show one immutable Fit receipt by exact uid instead of running Fit",
        ),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print one compact Fit result instead of opening the Viewer",
        ),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option(
            "--tui",
            help="Require the compact interactive Fit Viewer",
        ),
    ] = False,
) -> None:
    """Judge whether every supplied proposition can jointly hold."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)

        raw_propositions = tuple(propositions or ())
        raw_background = tuple(background or ())
        if ground_name is not None:
            if raw_propositions or raw_background:
                raise FitError(
                    "Choose proposition operands or --ground, not both."
                )

            def execute_ground(request: FitRequest) -> FitResult:
                store = MemoryStore(create=False)
                if request.receipt_uid is not None:
                    return run_fit_with_store(
                        request,
                        store=store,
                        provider_factory=connect_semantic_provider,
                    )
                with CommandProgress(
                    "FIT", "checking the complete Ground graph", total=1
                ) as progress:
                    result = run_fit_with_store(
                        request,
                        store=store,
                        provider_factory=connect_semantic_provider,
                    )
                    progress.update("receipt saved", step=1)
                return result

            runner = build_fit_console_runner(
                execute=execute_ground,
                clipboard_writer=write_system_clipboard,
                terminal=SystemTerminalCapabilities(),
            )
            runner.run(
                FitRequest(ground_name=ground_name, receipt_uid=receipt),
                mode=mode,
            )
            return

        if receipt is not None:
            raise FitError("--receipt requires the explicit --ground adapter.")
        request = FitPropositionsRequest(
            propositions=tuple(
                FitProposition(f"p{index}", content, "PROPOSITION")
                for index, content in enumerate(raw_propositions, 1)
            ),
            background=tuple(
                FitProposition(f"k{index}", content, "PROPOSITION")
                for index, content in enumerate(raw_background, 1)
            ),
        )

        def execute_propositions(next_request: FitPropositionsRequest):
            with CommandProgress(
                "FIT", "judging the complete proposition set", total=1
            ) as progress:
                result = run_proposition_fit(
                    next_request,
                    provider_factory=connect_semantic_provider,
                )
                progress.update("judgment complete", step=1)
            return result

        runner = build_proposition_fit_console_runner(
            execute=execute_propositions,
            clipboard_writer=write_system_clipboard,
            terminal=SystemTerminalCapabilities(),
        )
        runner.run(request, mode=mode)
    except (
        FitError,
        FitJudgmentError,
        ConsoleModeError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Fit error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
