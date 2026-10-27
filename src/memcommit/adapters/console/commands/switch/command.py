from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.adapters.console.terminal.components.context_picker import (
    choose_context,
    context_memory_rows,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.adapters.console.commands.switch.receipt import render_switch_context
from memcommit.adapters.console.commands.switch.setup import (
    SwitchTuiSetup,
    run_switch_tui,
)
from memcommit.persistence.store import ProfileStore
from memcommit.application.operations.switch.application import (
    SwitchContextError,
    SwitchContextRequest,
    resolve_switch_context_name,
)
from memcommit.application.operations.switch.runtime import (
    execute_switch_context,
    prepare_switch,
)


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Canonical Context name, or an explicit lexical relative "
                "selector such as '.', '..', './child', or '../sibling'; "
                "omit to enter the interactive Context picker"
            )
        ),
    ] = None,
) -> None:
    store = ProfileStore()
    expected_current = store.current_context_name()
    if name is None:
        try:
            snapshot = prepare_switch(
                store,
                expected_current=expected_current,
            )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if not snapshot.local_context_names:
            typer.secho(
                "Error: no contexts exist. Run 'mem init <name>' first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:

            def load_picker_memories(context_name: str):
                return context_memory_rows(store.load(context_name))

            request = run_switch_tui(
                SwitchTuiSetup(
                    expected_current=expected_current,
                    local_context_names=snapshot.local_context_names,
                    memory_loader=load_picker_memories,
                ),
                # Preserve the established command-level injection seam while
                # the concrete screen lives with its operation adapter.
                chooser=choose_context,
            )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(
                f"Error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if request is None:
            annotate_command_outcome("CANCELLED")
            typer.echo("Switch cancelled.")
            return
    else:
        try:
            selected = resolve_existing_context_access(
                store,
                name,
                current_name=expected_current,
            )
            request = SwitchContextRequest(
                selector=selected.name,
                expected_current=expected_current,
            )
        except (
            OSError,
            ProfileConfigError,
            ProfileError,
            RuntimeError,
            ValueError,
        ) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    try:
        target_name = resolve_switch_context_name(request)
        result = execute_switch_context(request, store=store)
    except SwitchContextError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except FileNotFoundError:
        typer.secho(
            f"Error: context '{target_name}' does not exist.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        typer.secho(
            f"Error: cannot switch to context '{target_name}': {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    render_switch_context(result)
