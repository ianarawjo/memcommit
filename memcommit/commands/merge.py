from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.store import MemoryStore


def cmd(other: Annotated[str, typer.Argument(help="Name of the context to merge into the current one")]) -> None:
    store = MemoryStore()
    if not store.context_exists(other):
        typer.secho(f"Error: context '{other}' does not exist.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        target = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if target.name == other:
        typer.secho("Error: cannot merge a context into itself.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    source = store.load(other)
    try:
        added = ops.merge(source, target)
    except ValueError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    mem_count = sum(1 for i in added if isinstance(i, Memory))
    ref_count = sum(1 for i in added if isinstance(i, MemoryRef))
    query_count = sum(1 for i in added if isinstance(i, QueryContextRef))
    ctx_count = sum(1 for i in added if isinstance(i, Context))
    parts = []
    if mem_count:
        parts.append(f"{mem_count} memor{'y' if mem_count == 1 else 'ies'}")
    if ref_count:
        parts.append(
            f"{ref_count} memory reference{'s' if ref_count != 1 else ''}"
        )
    if query_count:
        parts.append(
            f"{query_count} query-only context"
            f"{'s' if query_count != 1 else ''}"
        )
    if ctx_count:
        parts.append(f"{ctx_count} embedded context{'s' if ctx_count != 1 else ''}")
    summary = ", ".join(parts) if parts else "nothing new"

    store.save(target, AutoCheckpoint(
        command="merge",
        args={"source": other},
        description=f"Merged '{other}' into '{target.name}': added {summary}",
    ))
    typer.secho(f"Merged '{other}' into '{target.name}': added {summary}.", fg=typer.colors.GREEN)
