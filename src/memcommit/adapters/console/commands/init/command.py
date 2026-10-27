from typing import Annotated, Optional

from click import UsageError
import typer

from memcommit.application.operations.init.application import (
    ContextInitError,
    ContextInitRequest,
)
from memcommit.application.operations.init.runtime import (
    execute_context_init,
    prepare_context_init,
)
from memcommit.adapters.console.commands.init.receipt import render_context_init_receipt
from memcommit.persistence.store import ProfileStore


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            metavar="CONTEXT_NAME",
            show_default=False,
            help="Context name; create missing ancestors and reuse existing Contexts",
        ),
    ] = None,
) -> None:
    if name is None or not name.strip():
        raise UsageError("Missing required input. Example: mem init CONTEXT_NAME.")
    try:
        store = ProfileStore()
        snapshot = prepare_context_init(store)
        request = ContextInitRequest(
            name=name,
            create_parents=True,
            expected_current=snapshot.expected_current,
        )
        result = execute_context_init(request, store=store)
    except (ContextInitError, OSError, RuntimeError, TypeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_context_init_receipt(result)
