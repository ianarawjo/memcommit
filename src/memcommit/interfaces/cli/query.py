"""Plain command-line parsing and rendering for typed Query results."""

from __future__ import annotations

import typer

from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.application.operations.query.granted_application import GrantedQueryResponse
from memcommit.application.operations.query.ordinary_application import OrdinaryQueryResponse
from memcommit.application.operations.query.reference_application import QueryReferenceResponse


def render_ordinary_query_response(response: OrdinaryQueryResponse) -> None:
    """Render one ordinary grounded or explicitly ungrounded answer."""

    if not response.grounded:
        label, _, detail = response.answer.partition("\n")
        typer.secho(display_escape_text(label), bold=True)
        typer.echo(detail)
        return
    typer.echo(safe_terminal_text(response.answer))


def render_query_reference_response(response: QueryReferenceResponse) -> None:
    """Render one legacy reference answer through the terminal-safe boundary."""

    typer.echo(safe_terminal_text(response.answer))


def render_granted_query_response(response: GrantedQueryResponse) -> None:
    """Render one authorized granted answer."""

    typer.echo(safe_terminal_text(response.answer))


__all__ = [
    "render_granted_query_response",
    "render_ordinary_query_response",
    "render_query_reference_response",
]
