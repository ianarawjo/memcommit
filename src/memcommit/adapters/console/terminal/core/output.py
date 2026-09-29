"""Line-oriented output with terminal-safe replacement values."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text


def echo_text(template: str, *, err: bool = False, **values: object) -> None:
    """Echo an authored template with raw values escaped exactly once."""

    typer.echo(_format_text(template, values), err=err)


def secho_text(
    template: str,
    *,
    fg: str | None = None,
    bold: bool | None = None,
    err: bool = False,
    **values: object,
) -> None:
    """Echo a terminal-safe template with optional foreground color and boldness."""

    typer.secho(_format_text(template, values), fg=fg, bold=bold, err=err)


def _format_text(template: str, values: dict[str, object]) -> str:
    # Escape values first so the template's intentional layout remains intact.
    escaped = {name: display_escape_text(str(value)) for name, value in values.items()}
    return template.format_map(escaped)
