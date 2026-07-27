from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint, Memory
from memcommit.store import MemoryStore


def cmd(
    selector: Annotated[
        str,
        typer.Argument(help="UID (or unambiguous prefix) of the source memory"),
    ],
    source_name: Annotated[
        str,
        typer.Option("--from", help="Context that directly owns the source memory"),
    ],
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help="Context to add the reference to (defaults to current)",
        ),
    ] = None,
) -> None:
    store = MemoryStore()

    if not store.context_exists(source_name):
        typer.secho(
            f"Error: context '{source_name}' does not exist.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    target_name = into or store.current_context_name()
    if not target_name:
        typer.secho(
            "No current context. Pass --into or run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if not store.context_exists(target_name):
        typer.secho(
            f"Error: context '{target_name}' does not exist.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    source = store.load(source_name)
    target = store.load(target_name)
    try:
        item = ops.resolve(source, selector)
        if not isinstance(item, Memory):
            raise TypeError(
                f"'{selector}' is not a directly owned Memory in '{source_name}'."
            )
        ref = ops.reference_memory(item, source, target)
    except (KeyError, TypeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    store.save(
        target,
        AutoCheckpoint(
            command="reference",
            args={
                "reference_uid": ref.uid,
                "source": source_name,
                "memory_uid": item.uid,
                "into": target_name,
            },
            description=(
                f"Referenced [{item.uid[:8]}] from '{source_name}' "
                f"as [{ref.uid[:8]}] in '{target_name}'"
            ),
        ),
    )
    typer.secho(
        f"Referenced [{item.uid[:8]}] from '{source_name}' "
        f"as [{ref.uid[:8]}] in '{target_name}'.",
        fg=typer.colors.GREEN,
    )
