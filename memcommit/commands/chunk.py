from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.chunking import ChunkMethod
from memcommit.commands.granted_context import (
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def cmd(
    uid: Annotated[
        str,
        typer.Argument(help="UID (or unambiguous prefix) of the memory to chunk"),
    ],
    method: Annotated[
        ChunkMethod,
        typer.Option(
            "--method", "-m",
            help="Chunking strategy: markdown_headers | paragraphs | sentences",
            show_default=True,
        ),
    ] = ChunkMethod.paragraphs,
) -> None:
    active_store = MemoryStore()
    try:
        access = resolve_context_access(
            active_store,
            None,
            current_name=active_store.current_context_name(),
            required_permission="DELETE",
        )
        store = access.store
        ctx = store.load_direct(access.context_name)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        original, chunks = ops.chunk(ctx, uid, method)
    except (KeyError, TypeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if len(chunks) <= 1:
        typer.secho(
            f"Memory [{original.uid[:8]}] produced only {len(chunks)} chunk(s) "
            f"with method '{method.value}' — no changes made.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(0)

    # --- Preview & confirm ---
    n = len(chunks)
    typer.echo()
    typer.secho(
        f"Proposed split of [{original.uid[:8]}] → {n} chunks (method={method.value})",
        bold=True,
    )
    typer.echo("─" * 56)
    for i, chunk_mem in enumerate(chunks, 1):
        lines = chunk_mem.content.splitlines()
        header = lines[0][:60]
        typer.secho(f"  {i:>2}  {header}", fg=typer.colors.CYAN)
        for body_line in lines[1:6]:
            typer.secho(f"       {body_line[:60]}", dim=True)
        if len(lines) > 6:
            typer.secho("       …", dim=True)
    typer.echo("─" * 56)

    decision = typer.prompt(
        "Apply? [y/n]", default="", show_default=False
    ).strip().lower()

    if decision not in ("y", "yes"):
        typer.echo("Aborted — no changes made.")
        raise typer.Exit(0)

    original_position = ctx.ordered_uids().index(original.uid)
    ctx.remove(original.uid)
    for offset, chunk_mem in enumerate(chunks):
        ctx.add(chunk_mem, position=original_position + offset)

    try:
        with authorized_context_mutation(
            access,
            required_permissions=("CREATE", "DELETE"),
        ):
            store.save(
                ctx,
                AutoCheckpoint(
                    command="chunk",
                    args={
                        "uid": original.uid,
                        "method": method.value,
                        **grant_checkpoint_args(access),
                    },
                    description=(
                        f"Chunked [{original.uid[:8]}] → {n} memories "
                        f"({method.value})"
                    ),
                ),
            )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.secho(f"Done — {n} memories added.", fg=typer.colors.GREEN)
