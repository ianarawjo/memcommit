from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.batch_input import parse_add_lines, read_text_input
from memcommit.commands.paste_input import PasteCancelled, capture_paste
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
    paste: Annotated[
        bool,
        typer.Option(
            "--paste",
            help=(
                "Capture pasted text without echoing it, then add each "
                "non-empty line"
            ),
        ),
    ] = False,
) -> None:
    source_count = sum(
        (info is not None, input_source is not None, paste)
    )
    if source_count != 1:
        typer.secho(
            "Error: provide exactly one of INFO, --input, or --paste.",
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
    context_name = ctx.name
    context_uid = ctx.uid

    if info is not None:
        mem = ops.add(ctx, info)
        store.save(ctx, AutoCheckpoint(
            command="add",
            args={"content": info},
            description=f'Added: "{info[:80]}"',
        ))
        typer.secho(f"Added [{mem.uid[:8]}] {info}", fg=typer.colors.GREEN)
        return

    if paste:
        try:
            pasted_text = capture_paste()
        except PasteCancelled:
            typer.echo("Aborted — no changes made.")
            return
        except ValueError as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        try:
            contents = parse_add_lines(pasted_text)
        except ValueError as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        count = len(contents)
        noun = "line" if count == 1 else "lines"
        typer.secho(f"[{count} {noun} pasted]", dim=True)
        if not typer.confirm(
            f"Add {count} {'Memory' if count == 1 else 'Memories'} "
            f"to '{context_name}'?",
            default=False,
        ):
            typer.echo("Aborted — no changes made.")
            return

        # Capture and confirmation can take arbitrarily long. Reload immediately
        # before mutation so updates saved by another process are not overwritten
        # by the Context snapshot that was current when paste mode started.
        try:
            ctx = store.load(context_name)
        except (OSError, ValueError) as error:
            typer.secho(
                f"Error: could not reload context '{context_name}': {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if ctx.uid != context_uid:
            typer.secho(
                f"Error: context '{context_name}' was replaced while "
                "paste mode was open; no changes were made.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

        memories = ops.add_many(ctx, contents)
        store.save(
            ctx,
            AutoCheckpoint(
                command="add",
                args={
                    "mode": "paste",
                    "count": len(memories),
                    "contents": [
                        memory.content for memory in memories
                    ],
                },
                description=(
                    f"Added {len(memories)} memories from interactive paste"
                ),
            ),
        )
        # Paste mode intentionally reports only a count. The captured payload
        # should not be copied into terminal scrollback after confirmation.
        typer.secho(
            f"Added {len(memories)} "
            f"{'Memory' if len(memories) == 1 else 'Memories'} "
            f"to '{context_name}'.",
            fg=typer.colors.GREEN,
            bold=True,
        )
        return

    assert input_source is not None
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
