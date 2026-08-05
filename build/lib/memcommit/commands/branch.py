from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.store import (
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
    validate_context_name,
)


def cmd(name: Annotated[str, typer.Argument(help="Name for the new branch context")]) -> None:
    store = MemoryStore()
    source_name = store.current_context_name()
    if not source_name:
        typer.secho(
            "No current context. Run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        validate_context_name(name)
        if store.context_exists(name):
            raise FileExistsError(f"Context '{name}' already exists.")
        source = store.load_for_update(source_name)
        source_history = store.list_checkpoints(source_name)
        new_ctx = ops.branch(source, name)
        store.create_branch_context(
            new_ctx,
            source_name=source_name,
            expected_source_uid=source.uid,
            expected_source_digest=context_record_digest(source),
            expected_history_digest=checkpoint_history_digest(source_history),
            expected_current=source_name,
        )
    except (FileExistsError, FileNotFoundError, OSError, RuntimeError, ValueError) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.secho(
        f"Branched '{display_escape_text(source_name)}' → "
        f"'{display_escape_text(name)}' and switched to it.",
        fg=typer.colors.GREEN,
    )
