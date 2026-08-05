import shlex
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.granted_context import (
    GrantedReadStore,
    attached_grants,
    project_grants_into_context,
    resolve_context_access,
)
from memcommit.commands.tui_primitives import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def render_memory(memory: Memory, context_name: str) -> None:
    """Print one atomic memory in full."""
    typer.secho(f"Memory: {display_escape_text(memory.uid)}", bold=True)
    typer.echo(f"Context: {display_escape_text(context_name)}")
    typer.echo()
    typer.echo(safe_terminal_text(memory.content))


def render_memory_ref(memory_ref: MemoryRef, context_name: str) -> None:
    """Print one read-only Memory reference and its currently resolved content."""
    typer.secho(
        f"Memory reference: {display_escape_text(memory_ref.uid)}",
        bold=True,
    )
    typer.echo(f"Context: {display_escape_text(context_name)}")
    typer.echo(
        f"Source: {display_escape_text(memory_ref.target_context_name)} "
        f"[{display_escape_text(memory_ref.target_context_uid[:8])}]"
    )
    typer.echo("Target memory: " + display_escape_text(memory_ref.target_memory_uid))
    typer.echo("Mode: read-only live reference")
    typer.echo()
    if memory_ref.target is None:
        typer.secho(
            "(dangling reference: source context or memory is unavailable)",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.echo(safe_terminal_text(memory_ref.target.content))


def render_query_context_ref(
    query_ref: QueryContextRef,
    context_name: str,
) -> None:
    """Print query-only metadata without opening or revealing its source."""
    typer.secho(
        f"Query-only Context: {display_escape_text(query_ref.name)}",
        bold=True,
    )
    typer.echo(f"Reference: {display_escape_text(query_ref.uid)}")
    typer.echo(f"Parent Context: {display_escape_text(context_name)}")
    typer.echo("Mode: query-only research prototype")
    typer.echo("Content: concealed from mem ls and mem show")
    typer.echo()
    command = shlex.join(["mem", "query", query_ref.name, "<question>"])
    typer.echo(f"Ask with: {display_escape_text(command)}")


def render_context(ctx: Context) -> None:
    """Print the full direct contents of one context (non-recursive)."""
    items = list(ctx.iter_items())
    memories = [v for v in items if isinstance(v, Memory)]
    references = [v for v in items if isinstance(v, MemoryRef)]
    query_contexts = [v for v in items if isinstance(v, QueryContextRef)]
    embedded = [v for v in items if isinstance(v, Context)]

    typer.secho(f"Context: {display_escape_text(ctx.name)}", bold=True)
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
            typer.echo(
                f"  [context {display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.name)}"
            )
        elif isinstance(item, QueryContextRef):
            typer.echo(
                f"  [query   {display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.name)} (query-only)"
            )
        elif isinstance(item, MemoryRef):
            state = "read-only" if item.is_resolved else "dangling"
            typer.echo(
                f"  [ref     {display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.target_context_name)}#"
                f"{display_escape_text(item.target_memory_uid[:8])} "
                f"({state})"
            )
            if item.target is not None:
                typer.secho(
                    f"           {safe_terminal_text(item.target.content)}",
                    dim=True,
                )
        elif isinstance(item, Memory):
            memory = item
            typer.echo(
                f"  [memory  {display_escape_text(memory.uid[:8])}] ",
                nl=False,
            )
            typer.secho(safe_terminal_text(memory.content), dim=True)


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
    active_store = MemoryStore()
    try:
        current_name = active_store.current_context_name()
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=current_name,
            required_permission="READ",
        )
        if access.is_granted:
            ctx = GrantedReadStore(access).load(access.display_name)
        else:
            ctx = access.store.load(access.context_name)
            _, grants = attached_grants(access.context_name)
            if grants:
                ctx = project_grants_into_context(ctx, grants)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if selector is None:
        render_context(ctx)
        return

    try:
        item = ops.resolve(ctx, selector)
    except (KeyError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if isinstance(item, Memory):
        render_memory(item, ctx.name)
    elif isinstance(item, MemoryRef):
        render_memory_ref(item, ctx.name)
    elif isinstance(item, QueryContextRef):
        render_query_context_ref(item, ctx.name)
    elif isinstance(item, Context):
        render_context(item)
