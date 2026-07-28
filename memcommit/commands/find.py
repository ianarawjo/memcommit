import shlex
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.context import Memory, MemoryRef, QueryContextRef
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.search import FindError, SearchMatch
from memcommit.store import MemoryStore


def _render_content(content: str) -> None:
    for line in content.splitlines() or [""]:
        typer.echo(f"  {line}")


def _render_match(match: SearchMatch) -> None:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        typer.echo(
            f"[memory  {item.uid[:8]}] {candidate.context_name}"
        )
        _render_content(item.content)
    elif isinstance(item, MemoryRef):
        typer.echo(
            f"[ref     {item.uid[:8]}] {candidate.context_name} "
            f"-> {item.target_context_name}#{item.target_memory_uid[:8]}"
        )
        if item.target is not None:
            _render_content(item.target.content)
    elif isinstance(item, QueryContextRef):
        typer.echo(
            f"[query   {item.uid[:8]}] {candidate.context_name}"
        )
        typer.echo(f"  {item.name} (query-only)")
        command = shlex.join(
            [
                "mem",
                "query",
                item.name,
                "<question>",
                "--context",
                candidate.context_name,
            ]
        )
        typer.echo(
            f"  Ask with: {command}"
        )


def cmd(
    query: Annotated[
        str,
        typer.Argument(help="Natural-language query to find matching items"),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to search (defaults to current)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum matches to return (1-20)",
        ),
    ] = 5,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            help="Search direct items only; do not descend embedded Contexts",
        ),
    ] = False,
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
        matches = ops.find(
            ctx,
            query,
            connect_codex_chatgpt_provider,
            recursive=not direct,
            limit=limit,
        )
    except (FindError, QueryProviderError) as e:
        typer.secho(f"Find error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.secho(f"Context: {ctx.name}", bold=True)
    typer.echo(
        f"  {len(matches)} match{'es' if len(matches) != 1 else ''}"
    )
    if not matches:
        typer.echo("\n  (no matching items)")
        return
    for index, match in enumerate(matches):
        if index:
            typer.echo()
        _render_match(match)
