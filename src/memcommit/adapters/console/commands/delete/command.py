"""Delete one Memory, or the current Context and all its descendants."""

from typing import Annotated
from click import UsageError
import typer

from memcommit.adapters.console.commands.delete.receipt import (
    render_context_delete_warning,
    render_context_delete_result,
    render_removed_item,
)
from memcommit.adapters.console.terminal.components.errors import render_cli_error
from memcommit.application.operations.delete.application import (
    DirectItemDeleteRequest,
    run_direct_item_delete,
)
from memcommit.application.operations.delete.runtime import (
    MemoryStoreDeletePort,
    prepare_current_context_delete,
    apply_context_delete,
)
from memcommit.persistence.store import ProfileStore
from memcommit.persistence.command_ledger.attempts import annotate_command_outcome


def cmd(
    memory_selector: Annotated[
        str | None,
        typer.Argument(
            metavar="UID", help="One Memory UID or unique prefix in the current Context"
        ),
    ] = None,
    context: Annotated[
        bool,
        typer.Option(
            "--context",
            "-c",
            help="Delete the current Context and all descendants after confirmation.",
        ),
    ] = False,
) -> None:
    if context and memory_selector is not None:
        raise UsageError(
            "--context takes no name and cannot be combined with a Memory UID."
        )
    if not context and memory_selector is None:
        raise UsageError("Missing required input. Example: mem delete UID.")
    try:
        store = ProfileStore()
        if context:
            plan = prepare_current_context_delete(store)
            render_context_delete_warning(plan)
            if not typer.confirm("Continue?", default=False):
                annotate_command_outcome("CANCELLED")
                typer.echo("Delete cancelled.")
                return
            context_result = apply_context_delete(plan, store=store)
            render_context_delete_result(context_result)
            if context_result.cleanup_warning:
                raise typer.Exit(1)
            return
        result = run_direct_item_delete(
            DirectItemDeleteRequest(memory_selector),
            port=MemoryStoreDeletePort.capture(store),
        )
    except (typer.Exit, typer.Abort):
        raise
    except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
        render_cli_error(error)
        raise typer.Exit(1) from error
    render_removed_item(result)
