from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.store import MemoryStore, context_record_digest


def cmd(other: Annotated[str, typer.Argument(help="Name of the context to merge into the current one")]) -> None:
    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    current = snapshot.current_name
    if not current:
        typer.secho(
            "No current context. Run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        source_name = snapshot.resolve(other)
        if not store.context_exists(source_name):
            raise FileNotFoundError(
                f"Context '{source_name}' does not exist."
            )
        source = store.load_for_update(source_name)
        target = store.load_for_update(current)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if target.name == source_name:
        typer.secho("Error: cannot merge a context into itself.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

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

    try:
        store.save_context_with_sources(
            target,
            AutoCheckpoint(
                command="merge",
                args={"source": source_name},
                description=(
                    f"Merged '{source_name}' into '{target.name}': "
                    f"added {summary}"
                ),
            ),
            expected_context_digest=target._store_digest or "",
            source_bindings=(
                (source_name, source.uid, context_record_digest(source)),
            ),
        )
    except (OSError, RuntimeError, ValueError) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.secho(
        f"Merged '{display_escape_text(source_name)}' into "
        f"'{display_escape_text(target.name)}': added {summary}.",
        fg=typer.colors.GREEN,
    )
