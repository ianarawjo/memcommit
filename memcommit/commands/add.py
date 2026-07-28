from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.batch_input import parse_add_lines, read_text_input
from memcommit.context import AutoCheckpoint
from memcommit.store import MemoryStore


def cmd(
    info: Annotated[
        Optional[str],
        typer.Argument(help="Information to store (quote multi-word strings)"),
    ] = None,
    input_source: Annotated[
        Optional[str],
        typer.Option(
            "--input",
            "-i",
            help="Add each non-empty line from a UTF-8 file; use '-' for stdin",
        ),
    ] = None,
) -> None:
    if (info is None) == (input_source is None):
        typer.secho(
            "Error: provide exactly one of INFO or --input.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    store = MemoryStore()
    try:
        ctx = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if input_source is None:
        assert info is not None
        mem = ops.add(ctx, info)
        store.save(ctx, AutoCheckpoint(
            command="add",
            args={"content": info},
            description=f'Added: "{info[:80]}"',
        ))
        typer.secho(f"Added [{mem.uid[:8]}] {info}", fg=typer.colors.GREEN)
        return

    try:
        contents = parse_add_lines(read_text_input(input_source))
    except ValueError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    memories = ops.add_many(ctx, contents)
    store.save(
        ctx,
        AutoCheckpoint(
            command="add",
            args={
                "input": input_source,
                "mode": "lines",
                "count": len(memories),
                "contents": [memory.content for memory in memories],
            },
            description=(
                f"Added {len(memories)} memories from "
                f"{'stdin' if input_source == '-' else repr(input_source)}"
            ),
        ),
    )

    typer.secho(
        f"Added {len(memories)} memories to '{ctx.name}':",
        fg=typer.colors.GREEN,
        bold=True,
    )
    for memory in memories:
        typer.echo(f"  [{memory.uid[:8]}] {memory.content}")
