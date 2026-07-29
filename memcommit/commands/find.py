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


def _render_labeled_content(label: str, content: str) -> None:
    """Render the first content line beside its item and align continuations."""
    lines = content.splitlines() or [""]
    typer.echo(f"{label} {lines[0]}")
    continuation = " " * (len(label) + 1)
    for line in lines[1:]:
        typer.echo(f"{continuation}{line}")


def _render_match(match: SearchMatch) -> None:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        _render_labeled_content(
            f"[memory  {item.uid[:8]}]",
            item.content,
        )
    elif isinstance(item, MemoryRef):
        label = (
            f"[ref     {item.uid[:8]}] "
            f"-> {item.target_context_name}#{item.target_memory_uid[:8]}"
        )
        if item.target is not None:
            _render_labeled_content(label, item.target.content)
        else:
            typer.echo(label)
    elif isinstance(item, QueryContextRef):
        label = f"[query   {item.uid[:8]}]"
        typer.echo(f"{label} {item.name} (query-only)")
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
            f"{' ' * (len(label) + 1)}Ask with: {command}"
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

    if not matches:
        typer.secho(ctx.name, bold=True)
        typer.echo("  (no matching items)")
        return

    # Grouping makes the owning Context legible without repeating it on every
    # row. Dict insertion order keeps the model's first Context appearance,
    # while each group's rows retain their relative ranking.
    grouped: dict[tuple[str, str], list[SearchMatch]] = {}
    for match in matches:
        owner = (
            match.candidate.context_uid,
            match.candidate.context_name,
        )
        grouped.setdefault(owner, []).append(match)

    for group_index, ((_, owner_name), owner_matches) in enumerate(
        grouped.items()
    ):
        if group_index:
            typer.echo()
        typer.secho(owner_name, bold=True)
        for match in owner_matches:
            _render_match(match)
