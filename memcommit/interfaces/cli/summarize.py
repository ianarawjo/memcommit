"""Plain terminal renderer for a typed Summarize result."""

from __future__ import annotations

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.summarize import summarize_scope_label
from memcommit.interfaces.understanding import understanding_lines
from memcommit.summarize_application import SummarizeResult


def render_summarize_plain(result: SummarizeResult) -> None:
    """Preserve the established non-interactive human-readable output."""

    typer.secho(
        "SUMMARY · " + display_escape_text(result.context_name),
        bold=True,
    )
    typer.echo("STATUS · " + summarize_scope_label(result))
    typer.echo()
    for line in understanding_lines(result.understanding):
        typer.echo(line)
