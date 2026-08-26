"""Plain command-line parsing and rendering for typed Query results."""

from __future__ import annotations

import re
from typing import Sequence

import typer

from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.operations.query.granted_application import GrantedQueryResponse
from memcommit.operations.query.granted_source import AuthorityQueryCatalogEntry
from memcommit.operations.query.ordinary_application import OrdinaryQueryResponse
from memcommit.operations.query.reference_application import QueryReferenceResponse
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import source_object_label


_QUERY_MEMORY_SUFFIX = re.compile(r"(?P<view>.+)#(?P<handle>q-[0-9a-f]{12})\Z")


def split_query_memory_selector(selector: str) -> tuple[str, str | None]:
    """Split an exact opaque Memory handle from its query-view selector."""

    match = _QUERY_MEMORY_SUFFIX.fullmatch(selector)
    if match is None:
        return selector, None
    return match.group("view"), match.group("handle")


def render_ordinary_query_response(response: OrdinaryQueryResponse) -> None:
    """Render one ordinary grounded or explicitly ungrounded answer."""

    if not response.grounded:
        label, _, detail = response.answer.partition("\n")
        typer.secho(display_escape_text(label), bold=True)
        typer.echo(detail)
        return
    typer.echo(safe_terminal_text(response.answer))


def render_query_catalog(
    selector: str,
    catalog: Sequence[AuthorityQueryCatalogEntry],
) -> None:
    """Render opaque queryable Memory handles without opening source text."""

    query_view = source_object_label(SourceForm.QUERY_VIEW, title=True)
    typer.secho(f"{query_view} Memories: {display_escape_text(selector)}", bold=True)
    count = len(catalog)
    typer.echo(f"  {count} queryable Memor{'y' if count == 1 else 'ies'}")
    typer.echo()
    for entry in catalog:
        typer.echo(f"  [{entry.handle}]")
        for line in entry.placeholder_lines:
            typer.secho(f"    {line}", dim=True)
    typer.secho(
        "\nFlow Circular shapes preserve normalized word lengths and spacing; "
        "source text is not present.",
        dim=True,
    )
    typer.secho(
        "Ask one with: mem query '<VIEW>#<HANDLE>' 'QUESTION'",
        dim=True,
    )


def render_query_reference_response(response: QueryReferenceResponse) -> None:
    """Render one legacy reference answer through the terminal-safe boundary."""

    typer.echo(safe_terminal_text(response.answer))


def render_granted_query_response(response: GrantedQueryResponse) -> None:
    """Render either an opaque catalog or an authorized granted answer."""

    if response.answer is None:
        render_query_catalog(response.request.target.public_name, response.catalog)
        return
    typer.echo(safe_terminal_text(response.answer))


__all__ = [
    "render_granted_query_response",
    "render_ordinary_query_response",
    "render_query_catalog",
    "render_query_reference_response",
    "split_query_memory_selector",
]
