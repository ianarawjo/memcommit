"""Plain terminal presentation for a typed Summarize result."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.commands.search_explain.synthesize.summarize.scope_label import (
    summarize_scope_label,
)
from memcommit.application.operations.search_explain.synthesize.summarize.application import SummarizeResult


def render_summarize_plain(result: SummarizeResult) -> None:
    """Preserve the established non-interactive human-readable output."""

    typer.secho(
        "SUMMARY · " + display_escape_text(result.context_name),
        bold=True,
    )
    typer.echo("STATUS · " + summarize_scope_label(result))
    typer.echo()
    typer.echo(display_escape_text(result.understanding.text))
