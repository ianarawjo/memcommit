from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.branch_dialog import choose_branch_creation
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.context_targeting.tui.name_editor import suggest_fresh_context_name
from memcommit.store import (
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
    validate_context_name,
)


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Name for a new branch Context; omit in a terminal to choose "
                "a local Source, parent location, and exact fresh name"
            )
        ),
    ] = None,
) -> None:
    store = MemoryStore()
    expected_current = store.current_context_name()
    local_names = tuple(store.list_context_names())
    if name is None:
        if not local_names:
            typer.secho(
                "No local Contexts exist. Run 'mem init <name>' first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            receipt = choose_branch_creation(
                local_names,
                current=expected_current,
                suggest_name=lambda source: suggest_fresh_context_name(
                    f"{source}/branch",
                    local_names,
                ),
                validate_name=store.assert_context_creatable,
            )
        except (OSError, TypeError, ValueError) as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if receipt is None:
            typer.echo("Branch cancelled — no Context was changed.")
            return
        if receipt.source_name not in local_names:
            typer.secho(
                "Error: selected Branch Source is outside the frozen local catalog.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        source_name = receipt.source_name
        name = receipt.target_name
    else:
        source_name = expected_current
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
            expected_current=expected_current,
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
