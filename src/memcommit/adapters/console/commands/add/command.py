"""Typer adapter for adding one or more exact Memories."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.application.operations.add.application import (
    AddError,
    AddRequest,
    AddResult,
    run_add,
)
from memcommit.application.operations.add.input_records import (
    parse_line_input_records,
)
from memcommit.application.operations.add.runtime import MemoryStoreAddTargetPort
from memcommit.adapters.console.commands.add.receipt import render_add_receipt
from memcommit.adapters.console.clipboard import read_system_clipboard
from memcommit.adapters.console.terminal.components.errors import render_cli_error
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.commands.add.workbench import (
    build_add_workbench_setup,
    run_add_workbench,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def _run_interactive_add(
    *,
    specified_context_locator: str | None,
) -> AddResult | None:
    require_interactive_terminal(
        "Interactive Add",
        snapshot_hint="Pass positional MEMORY values or --paste outside a terminal.",
    )
    store = MemoryStore()
    current_name = store.current_context_name()
    port = MemoryStoreAddTargetPort(store, current_name=current_name)
    setup = build_add_workbench_setup(
        store,
        current_name=current_name,
        specified_context_locator=specified_context_locator,
    )
    return run_add_workbench(
        setup=setup,
        execute=lambda request: run_add(request, target_port=port),
        require_tty=False,
    )


def _run_direct_add(
    *,
    contents: tuple[str, ...],
    paste: bool,
    specified_context_locator: str | None,
) -> AddResult:
    # Capture global navigation before clipboard intake can yield control.
    # Relative target meaning stays stable for this command.
    store = MemoryStore()
    current_name = store.current_context_name()
    port = MemoryStoreAddTargetPort(store, current_name=current_name)
    if paste:
        contents = parse_line_input_records(read_system_clipboard())
    request = AddRequest(
        context_locator=specified_context_locator,
        contents=contents,
    )
    return run_add(
        request,
        target_port=port,
    )


def cmd(
    memories: Annotated[
        Optional[list[str]],
        typer.Argument(
            metavar="[MEMORY]...",
            help="Add one Memory per positional value; quote spaces within one Memory",
        ),
    ] = None,
    paste: Annotated[
        bool,
        typer.Option(
            "--paste",
            help="Add each non-empty line from the system clipboard",
        ),
    ] = False,
    specified_context_locator: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            "--context",
            "-c",
            metavar="CONTEXT",
            help=(
                "Target Context to receive the Memories; --context/-c are compatibility aliases"
            ),
        ),
    ] = None,
) -> None:
    contents = tuple(memories or ())
    if contents and paste:
        typer.secho(
            "Error: cannot combine direct MEMORY arguments with --paste; use one or the other.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        if not contents and not paste:
            result = _run_interactive_add(
                specified_context_locator=specified_context_locator,
            )
            if result is None:
                typer.echo("Add cancelled — no changes made.")
                return
        else:
            result = _run_direct_add(
                contents=contents,
                paste=paste,
                specified_context_locator=specified_context_locator,
            )
    except (
        AddError,
        ConcurrentContextUpdateError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        render_cli_error(error)
        raise typer.Exit(1)

    render_add_receipt(result)
