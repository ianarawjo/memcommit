from typing import Annotated, Optional

import typer

from memcommit.application.operations.context_init.application import (
    ContextInitError,
    ContextInitRequest,
)
from memcommit.application.operations.context_init.runtime import (
    execute_context_init,
    prepare_context_init,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import choose_context_name
from memcommit.adapters.console.commands.init.receipt import render_context_init
from memcommit.adapters.console.commands.init.choose_name import (
    ContextInitTuiSetup,
    run_context_init_tui,
)
from memcommit.persistence.store import MemoryStore, validate_context_name


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Unique portable non-UID-shaped name for the new Context; "
                "omit to use the interactive picker"
            ),
        ),
    ] = None,
    parents: Annotated[
        bool,
        typer.Option(
            "--parents",
            "-p",
            help=(
                "Create missing lexical parent Contexts and reuse existing "
                "prefixes; does not embed children"
            ),
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    snapshot = prepare_context_init(store)
    try:
        if name is None:
            request = run_context_init_tui(
                setup=ContextInitTuiSetup(
                    expected_current=snapshot.expected_current,
                    context_names=snapshot.context_names,
                    validate_name=(
                        validate_context_name
                        if parents
                        else store.assert_context_creatable
                    ),
                ),
                create_parents=parents,
                # Preserve the historical command-level injection seam while
                # the concrete TUI implementation lives with its adapter.
                chooser=choose_context_name,
            )
            if request is None:
                typer.echo("Initialization cancelled — no Context was created.")
                return
        else:
            request = ContextInitRequest(
                name=name,
                create_parents=parents,
                expected_current=snapshot.expected_current,
            )
        result = execute_context_init(request, store=store)
    except (ContextInitError, OSError, RuntimeError, TypeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_context_init(result)
