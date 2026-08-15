"""Run and inspect revision-bound Fit judgments for one Ground."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.bootstrap import build_fit_console_runner
from memcommit.clipboard import write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.fit import FitError, FitReport
from memcommit.fit_application import FitRequest, FitResult
from memcommit.fit_runtime import run_fit_with_store
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
    ground_name: Annotated[
        str,
        typer.Argument(help="Saved Ground whose active Examples are fitted"),
    ],
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
    """Fit every active Ground Example to the active Rules without changing Ground."""

    try:
        mode = resolve_console_mode(plain=plain, tui=tui)

        def execute(request: FitRequest) -> FitResult:
            store = MemoryStore(create=False)
            if request.receipt_uid is not None:
                return run_fit_with_store(
                    request,
                    store=store,
                    provider_factory=connect_semantic_provider,
                )
            with CommandProgress("FIT", "judging every Ground Example", total=1) as progress:
                result = run_fit_with_store(
                    request,
                    store=store,
                    provider_factory=connect_semantic_provider,
                )
                progress.update("receipt saved", step=1)
            return result

        runner = build_fit_console_runner(
            execute=execute,
            clipboard_writer=write_system_clipboard,
            terminal=SystemTerminalCapabilities(),
        )
        runner.run(
            FitRequest(ground_name=ground_name, receipt_uid=receipt),
            mode=mode,
        )
    except (
        FitError,
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
