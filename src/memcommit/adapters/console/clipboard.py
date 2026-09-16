"""System-text clipboard support for console commands."""

from __future__ import annotations

import subprocess
import sys
from typing import Callable


_CLIPBOARD_TIMEOUT_SECONDS = 5


class ClipboardError(RuntimeError):
    """A system clipboard operation could not be completed."""


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _clipboard_command(name: str, *, platform_name: str | None = None) -> list[str]:
    platform_value = platform_name or sys.platform
    if platform_value != "darwin":
        raise ClipboardError(
            "System clipboard integration is currently available only on macOS."
        )
    return [f"/usr/bin/{name}"]


def write_system_clipboard(
    text: str,
    *,
    runner: Runner | None = None,
    platform_name: str | None = None,
) -> None:
    """Write exact UTF-8 text to the platform clipboard."""
    run = runner or subprocess.run
    command = _clipboard_command("pbcopy", platform_name=platform_name)
    try:
        result = run(
            command,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=_CLIPBOARD_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ClipboardError("Could not write to the system clipboard.") from error
    if result.returncode != 0:
        raise ClipboardError("Could not write to the system clipboard.")


def read_system_clipboard(
    *,
    runner: Runner | None = None,
    platform_name: str | None = None,
) -> str:
    """Read exact UTF-8 text from the platform clipboard."""
    run = runner or subprocess.run
    command = _clipboard_command("pbpaste", platform_name=platform_name)
    try:
        result = run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=_CLIPBOARD_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ClipboardError("Could not read the system clipboard.") from error
    if result.returncode != 0:
        raise ClipboardError("Could not read the system clipboard.")
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ClipboardError(
            "The system clipboard does not contain valid UTF-8 text."
        ) from error
