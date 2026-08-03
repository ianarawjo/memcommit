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


def cmd(uid: Annotated[str, typer.Argument(help="UID (or unambiguous prefix) of the item to remove")]) -> None:
    store = MemoryStore()
    try:
        ctx = store.load_current_direct()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        item = ops.remove(ctx, uid)
    except (KeyError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if isinstance(item, Memory):
        description = f'Removed memory [{item.uid[:8]}]: "{item.content[:80]}"'
    elif isinstance(item, MemoryRef):
        description = (
            f"Removed memory reference [{item.uid[:8]}] to "
            f"'{item.target_context_name}' [{item.target_memory_uid[:8]}]"
        )
    elif isinstance(item, QueryContextRef):
        description = (
            f"Removed query-only Context '{item.name}' [{item.uid[:8]}]"
        )
    elif isinstance(item, Context):
        description = f"Removed embedded context '{item.name}' [{item.uid[:8]}]"

    store.save(ctx, AutoCheckpoint(
        command="remove",
        args={"uid": item.uid},
        description=description,
    ))

    if isinstance(item, Memory):
        typer.secho(f"Removed [{item.uid[:8]}] {item.content}", fg=typer.colors.GREEN)
    elif isinstance(item, MemoryRef):
        typer.secho(
            f"Removed reference [{item.uid[:8]}] to "
            f"'{item.target_context_name}' [{item.target_memory_uid[:8]}].",
            fg=typer.colors.GREEN,
        )
    elif isinstance(item, QueryContextRef):
        typer.secho(
            f"Removed query-only Context '{item.name}' [{item.uid[:8]}].",
            fg=typer.colors.GREEN,
        )
    elif isinstance(item, Context):
        typer.secho(f"Removed embedded context '{item.name}' [{item.uid[:8]}]", fg=typer.colors.GREEN)
