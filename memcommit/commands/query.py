"""Ask a question of an opaque query-only Context."""

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.tui_primitives import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.context import QueryContextRef
from memcommit.query_provider import QueryProviderError, connect_query_provider
from memcommit.store import MemoryStore


def cmd(
    selector: Annotated[
        str,
        typer.Argument(help="Query-only Context name or reference UID/prefix"),
    ],
    question: Annotated[
        str,
        typer.Argument(help="Question to answer from the concealed source"),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Parent context containing the query-only reference",
        ),
    ] = None,
    language: Annotated[
        str,
        typer.Option(
            "--language",
            "-l",
            help=(
                "Concealed source language to query; exact translations "
                "must cover the whole source"
            ),
        ),
    ] = "en",
) -> None:
    store = MemoryStore()
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        selected_name = context_snapshot.resolve_or_current(context_name)
        if not selected_name:
            raise RuntimeError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        ctx = store.load(selected_name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        item = ops.resolve(ctx, selector)
    except (KeyError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if not isinstance(item, QueryContextRef):
        typer.secho(
            f"Error: '{display_escape_text(selector)}' is not a query-only Context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if not question.strip():
        typer.secho(
            "Error: question must be non-empty.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    # Authenticate the provider before opening the concealed local source.
    try:
        provider = connect_query_provider(item.provider)
    except QueryProviderError as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        source = store.load_query_source(
            item.target_source_uid,
            expected_name=item.name,
            language=language,
        )
        answer = provider.query(source.name, source.content, question)
    except (
        FileNotFoundError,
        ValueError,
        QueryProviderError,
    ) as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(safe_terminal_text(answer))
