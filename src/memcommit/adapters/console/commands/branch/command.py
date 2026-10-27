"""Branch the current Context, optionally including its lexical descendants."""

from typing import Annotated

from click import UsageError
import typer

from memcommit.adapters.console.commands.branch.receipt import render_branch_receipt
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.branch.application import BranchRequest
from memcommit.application.operations.branch.runtime import execute_branch, prepare_branch
from memcommit.persistence.store import ProfileStore


def cmd(
    name: Annotated[
        str | None,
        typer.Argument(
            metavar="NEW_CONTEXT_NAME",
            show_default=False,
            help="New Context name for a branch of the current Context",
        ),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r", "--recursive",
            help="Branch the current Context and all lexical descendants",
        ),
    ] = False,
) -> None:
    if name is None or not name.strip():
        raise UsageError("Missing required input. Example: mem branch NEW_CONTEXT_NAME.")
    try:
        store = ProfileStore()
        setup = prepare_branch(store)
        source_name = setup.expected_current
        if source_name is None:
            raise ValueError("No current Context. Run 'mem init CONTEXT_NAME' first.")
        result = execute_branch(
            BranchRequest(
                source_name=source_name,
                target_name=name,
                include_descendants=recursive,
                expected_current=source_name,
                local_context_names=setup.local_context_names,
            ),
            store=store,
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1) from error
    render_branch_receipt(result)
