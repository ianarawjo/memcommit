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
from memcommit.persistence.store import MemoryStore
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
    previous: Annotated[
        bool,
        typer.Option(
            "-p",
            "--previous",
            help="Switch to the previous Context in navigation history",
        ),
    ] = False,
    next_: Annotated[
        bool,
        typer.Option(
            "-n",
            "--next",
            help="Switch to the next Context after moving backward",
        ),
    ] = False,
) -> None:
    if previous and next_:
        raise typer.BadParameter("--previous and --next cannot be used together.")
    if name is not None and (previous or next_):
        raise typer.BadParameter(
            "A Context name cannot be combined with --previous or --next."
        )

    store = MemoryStore()
    expected_current = store.current_context_name()
    if previous or next_:
        request = SwitchContextRequest(
            selector=None,
            expected_current=expected_current,
            direction="PREVIOUS" if previous else "NEXT",
        )
    elif name is None:
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
        target_name = (
            resolve_switch_context_name(request)
            if request.selector is not None
            else None
        )
        result = execute_switch_context(request, store=store)
    except SwitchContextError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except FileNotFoundError:
        message = (
            f"context '{target_name}' does not exist."
            if target_name is not None
            else "saved navigation Context does not exist."
        )
        typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        target_label = (
            f"context '{target_name}'"
            if target_name is not None
            else (
                "the previous Context"
                if request.direction == "PREVIOUS"
                else "the next Context"
            )
        )
        typer.secho(
            f"Error: cannot switch to {target_label}: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    render_switch_context(result)
