"""Plain command-line rendering for typed Query results."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.application.operations.query.ordinary_application import (
    OrdinaryQueryResponse,
)


def render_ordinary_query_response(response: OrdinaryQueryResponse) -> None:
    """Render one ordinary grounded or explicitly ungrounded answer."""

    if not response.grounded:
        label, _, detail = response.answer.partition("\n")
        typer.secho(display_escape_text(label), bold=True)
        typer.echo(detail)
        return
    typer.echo(safe_terminal_text(response.answer))


__all__ = [
    "render_ordinary_query_response",
]
