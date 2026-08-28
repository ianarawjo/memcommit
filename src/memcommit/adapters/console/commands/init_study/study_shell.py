"""Post-command Study shell lifecycle owned by ``init-study``."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text


STUDY_SHELL_ENV = "MEMCOMMIT_STUDY_SHELL"
STUDY_PROFILE_ENV = "MEMCOMMIT_STUDY_PROFILE"
ShellRunner = Callable[..., subprocess.CompletedProcess[object]]


def should_enter_study_shell(
    *,
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Return whether this invocation owns a new interactive Study shell."""

    active_environment = os.environ if environment is None else environment
    return (
        active_environment.get(STUDY_SHELL_ENV) != "1"
        and sys.stdin.isatty()
        and sys.stdout.isatty()
        and sys.stderr.isatty()
    )


def run_study_shell(
    profile_name: str,
    *,
    shell_path: str | None = None,
    runner: ShellRunner = subprocess.run,
    environment: Mapping[str, str] | None = None,
) -> int:
    """Run one isolated zsh whose in-memory and file history are run-local."""

    if not isinstance(profile_name, str) or not profile_name:
        raise ValueError("Study shell requires a nonempty Profile name.")
    executable = shell_path or shutil.which("zsh")
    if executable is None:
        raise RuntimeError("Study shell requires zsh, but zsh is unavailable.")
    active_environment = dict(os.environ if environment is None else environment)

    with tempfile.TemporaryDirectory(prefix="memcommit-study-shell-") as directory:
        root = Path(directory)
        child_environment = dict(active_environment)
        child_environment.update(
            {
                STUDY_SHELL_ENV: "1",
                STUDY_PROFILE_ENV: profile_name,
                "HISTFILE": str(root / "history"),
                "SAVEHIST": "0",
                # Both user and global startup files are skipped below. This
                # private ZDOTDIR is a second boundary against inherited shell
                # configuration reattaching the person's ordinary history.
                "ZDOTDIR": str(root),
                "PROMPT": f"study:{profile_name}%# ",
            }
        )
        try:
            result = runner(
                (executable, "-d", "-f", "-i"),
                check=False,
                env=child_environment,
            )
        except KeyboardInterrupt:
            return 130
        except OSError as error:
            raise RuntimeError(f"Could not start the Study shell: {error}") from error
    return int(result.returncode)


def schedule_study_shell(
    ctx: typer.Context,
    profile_name: str,
    *,
    runner: ShellRunner = subprocess.run,
) -> None:
    """Enter the Study shell after the root command attempt is finalized."""

    def enter() -> None:
        typer.secho(
            "Entering isolated Study shell · exit returns to the previous shell.",
            fg=typer.colors.CYAN,
        )
        try:
            exit_code = run_study_shell(profile_name, runner=runner)
        except (RuntimeError, ValueError) as error:
            typer.secho(
                "Study shell error: " + display_escape_text(str(error)),
                fg=typer.colors.RED,
                err=True,
            )
            return
        typer.echo(f"Exited Study shell · status {exit_code}.")

    ctx.find_root().call_on_close(enter)


__all__ = [
    "STUDY_PROFILE_ENV",
    "STUDY_SHELL_ENV",
    "run_study_shell",
    "schedule_study_shell",
    "should_enter_study_shell",
]
