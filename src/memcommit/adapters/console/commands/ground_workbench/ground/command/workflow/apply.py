"""Execute one explicitly approved logical ``mem ground`` command."""

from __future__ import annotations

import subprocess
import sys

from memcommit.application.operations.ground_workbench.ground.contracts import GroundError


def _run_approved_ground_command(
    argv: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    """Execute an approved logical ``mem`` argv without invoking a shell."""
    if len(argv) < 2 or argv[:2] != ("mem", "ground"):
        raise GroundError("The approved command is not a Ground command.")
    return subprocess.run(
        [sys.executable, "-m", "memcommit.adapters.console.entrypoint", *argv[1:]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
