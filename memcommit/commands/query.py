"""Ask a question of an opaque query-only Context."""
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
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
        ctx = (
            store.load_current()
            if context_name is None
            else store.load(context_name)
        )
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        item = ops.resolve(ctx, selector)
    except (KeyError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if not isinstance(item, QueryContextRef):
        typer.secho(
            f"Error: '{selector}' is not a query-only Context.",
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
    except QueryProviderError as e:
        typer.secho(f"Query error: {e}", fg=typer.colors.RED, err=True)
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
    ) as e:
        typer.secho(f"Query error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.echo(answer)
