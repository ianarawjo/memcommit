"""Replace the content of one Memory in the current Context."""

from typing import Annotated

from click import UsageError
import typer

from memcommit.adapters.console.commands.edit.receipt import render_edit_receipt
from memcommit.adapters.console.terminal.components.errors import render_cli_error
from memcommit.application.operations.edit.application import EditRequest, run_edit
from memcommit.application.operations.edit.runtime import MemoryStoreEditPort
from memcommit.persistence.store import ProfileStore


def cmd(
    memory_selector: Annotated[
        str | None,
        typer.Argument(
            metavar="UID", help="One Memory UID or unique prefix in the current Context"
        ),
    ] = None,
    content: Annotated[
        str | None,
        typer.Argument(
            metavar="CONTENT", help="Exact replacement content for the selected Memory"
        ),
    ] = None,
) -> None:
    if memory_selector is None or content is None:
        raise UsageError('Missing required input. Example: mem edit UID "New content".')
    try:
        store = ProfileStore()
        result = run_edit(
            EditRequest(memory_selector, content),
            port=MemoryStoreEditPort.capture(store),
        )
    except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
        render_cli_error(error)
        raise typer.Exit(1) from error
    render_edit_receipt(result)
