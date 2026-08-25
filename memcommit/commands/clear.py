from typing import Annotated, Optional

import typer

from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.interfaces.console.text import display_escape_text
from memcommit.operations.clear.application import ClearRequest
from memcommit.operations.clear.runtime import execute_clear
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def cmd(
    context_name: Annotated[
        Optional[str], typer.Argument(help="Context to clear (defaults to current)")
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "-R",
            "--recursive",
            help=(
                "Clear direct items from the selected local Context and every "
                "lexical descendant as one Undoable command."
            ),
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "-f",
            "--force",
            hidden=True,
        ),
    ] = False,
) -> None:
    active_store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(active_store)
    # ``--force`` remains accepted for scripts written against the former
    # prompt. Invocation is now the approval boundary because the operation is
    # checkpointed and immediately Undoable.
    del force
    try:
        result = execute_clear(
            active_store,
            ClearRequest(
                context_locator=context_name,
                recursive=recursive,
            ),
            current_name=snapshot.current_name,
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    display_name = display_escape_text(result.context_name)
    if not result.changed:
        noun = "subtree" if result.recursive else "Context"
        typer.secho(
            f"{noun} '{display_name}' is already empty.",
            fg=typer.colors.YELLOW,
        )
        return

    if result.recursive:
        scope = (
            f"{result.changed_context_count} Context(s)"
            if result.changed_context_count == result.scope_count
            else (
                f"{result.changed_context_count} of {result.scope_count} "
                "Context(s)"
            )
        )
        typer.secho(
            f"Cleared {result.item_count} item(s) from {scope} under "
            f"'{display_name}'. Undo can restore this command as one unit.",
            fg=typer.colors.GREEN,
        )
        return

    typer.secho(
        f"Cleared {result.item_count} item(s) from '{display_name}'.",
        fg=typer.colors.GREEN,
    )
