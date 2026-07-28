import shlex
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.store import MemoryStore


def render_memory(memory: Memory, context_name: str) -> None:
    """Print one atomic memory in full."""
    typer.secho(f"Memory: {memory.uid}", bold=True)
    typer.echo(f"Context: {context_name}")
    typer.echo()
    typer.echo(memory.content)


def render_memory_ref(memory_ref: MemoryRef, context_name: str) -> None:
    """Print one read-only Memory reference and its currently resolved content."""
    typer.secho(f"Memory reference: {memory_ref.uid}", bold=True)
    typer.echo(f"Context: {context_name}")
    typer.echo(
        f"Source: {memory_ref.target_context_name} "
        f"[{memory_ref.target_context_uid[:8]}]"
    )
    typer.echo(f"Target memory: {memory_ref.target_memory_uid}")
    typer.echo("Mode: read-only live reference")
    typer.echo()
    if memory_ref.target is None:
        typer.secho(
            "(dangling reference: source context or memory is unavailable)",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.echo(memory_ref.target.content)


def render_query_context_ref(
    query_ref: QueryContextRef,
    context_name: str,
) -> None:
    """Print query-only metadata without opening or revealing its source."""
    typer.secho(f"Query-only Context: {query_ref.name}", bold=True)
    typer.echo(f"Reference: {query_ref.uid}")
    typer.echo(f"Parent Context: {context_name}")
    typer.echo("Mode: query-only research prototype")
    typer.echo("Content: concealed from mem ls and mem show")
    typer.echo()
    command = shlex.join(
        ["mem", "query", query_ref.name, "<question>"]
    )
    typer.echo(f"Ask with: {command}")


def render_context(ctx: Context) -> None:
    """Print the full direct contents of one context (non-recursive)."""
    items = list(ctx.iter_items())
    memories = [v for v in items if isinstance(v, Memory)]
    references = [v for v in items if isinstance(v, MemoryRef)]
    query_contexts = [v for v in items if isinstance(v, QueryContextRef)]
    embedded = [v for v in items if isinstance(v, Context)]

    typer.secho(f"Context: {ctx.name}", bold=True)
    typer.echo(
        f"  {len(memories)} memor{'y' if len(memories) == 1 else 'ies'}"
        f"  |  {len(references)} memory reference{'s' if len(references) != 1 else ''}"
        f"  |  {len(query_contexts)} query-only context{'s' if len(query_contexts) != 1 else ''}"
        f"  |  {len(embedded)} embedded context{'s' if len(embedded) != 1 else ''}"
    )

    if not items:
        typer.echo("\n  (no items)")
        return

    typer.secho("\nItems (in context order):", bold=True)
    for item in items:
        if isinstance(item, Context):
            typer.echo(f"  [context {item.uid[:8]}] {item.name}")
        elif isinstance(item, QueryContextRef):
            typer.echo(
                f"  [query   {item.uid[:8]}] {item.name} (query-only)"
            )
        elif isinstance(item, MemoryRef):
            state = "read-only" if item.is_resolved else "dangling"
            typer.echo(
                f"  [ref     {item.uid[:8]}] "
                f"{item.target_context_name}#{item.target_memory_uid[:8]} "
                f"({state})"
            )
            if item.target is not None:
                typer.secho(f"           {item.target.content}", dim=True)
        elif isinstance(item, Memory):
            memory = item
            typer.echo(f"  [memory  {memory.uid[:8]}] ", nl=False)
            typer.secho(memory.content, dim=True)


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help="Item UID/prefix or exact embedded-context name; omit to show the whole context"
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Parent context to inspect (defaults to current)",
        ),
    ] = None,
) -> None:
    store = MemoryStore()

    if context_name is None:
        try:
            ctx = store.load_current()
        except RuntimeError as e:
            typer.secho(str(e), fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
    else:
        if not store.context_exists(context_name):
            typer.secho(
                f"Error: context '{context_name}' not found.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        ctx = store.load(context_name)

    if selector is None:
        render_context(ctx)
        return

    try:
        item = ops.resolve(ctx, selector)
    except (KeyError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if isinstance(item, Memory):
        render_memory(item, ctx.name)
    elif isinstance(item, MemoryRef):
        render_memory_ref(item, ctx.name)
    elif isinstance(item, QueryContextRef):
        render_query_context_ref(item, ctx.name)
    elif isinstance(item, Context):
        render_context(item)
