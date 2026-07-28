from typing import Annotated, Optional

import typer

from memcommit.context import (
    Context,
    Information,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.store import MemoryStore


def _one_line(content: str) -> str:
    """Render atomic Memory content as its compact, human-readable name."""
    return " ".join(content.split()) or "(empty)"


def _grouped_items(
    ctx: Context,
) -> tuple[list[Context | QueryContextRef], list[Memory | MemoryRef]]:
    """Return context-like items first, preserving order within each group."""
    contexts: list[Context | QueryContextRef] = []
    memories: list[Memory | MemoryRef] = []
    for item in ctx.iter_items():
        if isinstance(item, (Context, QueryContextRef)):
            contexts.append(item)
        else:
            memories.append(item)
    return contexts, memories


def _render_item(item: Information, indent: int) -> None:
    prefix = " " * indent
    if isinstance(item, Context):
        typer.echo(f"{prefix}[context {item.uid[:8]}] {item.name}")
    elif isinstance(item, QueryContextRef):
        typer.echo(
            f"{prefix}[query   {item.uid[:8]}] {item.name} (query-only)"
        )
    elif isinstance(item, MemoryRef):
        if item.target is None:
            typer.echo(
                f"{prefix}[ref     {item.uid[:8]}] (dangling) "
                f"{item.target_context_name}#{item.target_memory_uid[:8]}"
            )
        else:
            typer.echo(
                f"{prefix}[ref     {item.uid[:8]}] "
                f"{_one_line(item.target.content)} "
                f"-> {item.target_context_name}#{item.target_memory_uid[:8]}"
            )
    else:
        typer.echo(f"{prefix}[memory  {item.uid[:8]}] {_one_line(item.content)}")


def _render_contents(
    ctx: Context,
    *,
    indent: int,
    recursive: bool,
    ancestors: frozenset[str],
) -> None:
    """Render one Context's children, optionally descending into child Contexts."""
    contexts, memories = _grouped_items(ctx)
    for child in contexts:
        _render_item(child, indent)
        if not recursive or isinstance(child, QueryContextRef):
            continue
        child_indent = indent + 2
        if child.uid in ancestors:
            typer.echo(f"{' ' * child_indent}(cycle)")
        elif not child.memories:
            typer.echo(f"{' ' * child_indent}(no items)")
        else:
            _render_contents(
                child,
                indent=child_indent,
                recursive=True,
                ancestors=ancestors | {child.uid},
            )
    for item in memories:
        _render_item(item, indent)


def render_index(ctx: Context, *, recursive: bool = False) -> None:
    """Print a compact index of a Context's logical children."""
    typer.secho(f"Context: {ctx.name}", bold=True)
    count = len(ctx.memories)
    typer.echo(f"  {count} item{'s' if count != 1 else ''}")

    if not ctx.memories:
        typer.echo("\n  (no items)")
        return

    typer.echo()
    _render_contents(
        ctx,
        indent=2,
        recursive=recursive,
        ancestors=frozenset({ctx.uid}),
    )


def cmd(
    context_name: Annotated[Optional[str], typer.Argument(help="Context to list (defaults to current)")] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "-R",
            "--recursive",
            help="Recursively list the contents of embedded Contexts.",
        ),
    ] = False,
) -> None:
    store = MemoryStore()

    if context_name is None:
        context_name = store.current_context_name()
        if not context_name:
            typer.secho("No current context. Run 'mem init <name>' first.", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    if not store.context_exists(context_name):
        typer.secho(f"Error: context '{context_name}' not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_index(store.load(context_name), recursive=recursive)
