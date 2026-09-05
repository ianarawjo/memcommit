"""Typer adapter for adding one or more exact Memories."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.application.operations.add.application import (
    AddedMemory,
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
from memcommit.application.operations.show.application import ShowMemory, ShowRequest
from memcommit.application.operations.show.runtime import execute_show
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def load_add_memories(
    name: str,
    *,
    store: MemoryStore,
    current_context_name: str | None,
) -> tuple[AddedMemory, ...]:
    """Use the existing READ boundary instead of reading through the mutation port."""

    result = execute_show(
        ShowRequest(context_name=name, current_context_name=current_context_name),
        store=store,
        allow_grants=True,
    )
    return tuple(
        AddedMemory(uid=item.uid, content=item.content)
        for item in result.contexts[0].items
        if isinstance(item, ShowMemory)
    )


def _run_interactive_add(
    *,
    specified_context_locator: str | None,
) -> tuple[AddResult, ...]:
    require_interactive_terminal(
        "Interactive Add",
        snapshot_hint="Pass positional MEMORY values or --paste outside a terminal.",
    )
    store = MemoryStore()
    current_context_name = store.current_context_name()
    port = MemoryStoreAddTargetPort(
        store,
        current_context_name=current_context_name,
    )
    setup = build_add_workbench_setup(
        store,
        current_context_name=current_context_name,
        specified_context_locator=specified_context_locator,
    )
    return run_add_workbench(
        setup=setup,
        execute=lambda request: run_add(request, target_port=port),
        load_memories=lambda name: load_add_memories(
            name, store=store, current_context_name=current_context_name
        ),
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
    current_context_name = store.current_context_name()
    port = MemoryStoreAddTargetPort(
        store,
        current_context_name=current_context_name,
    )
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
            results = _run_interactive_add(
                specified_context_locator=specified_context_locator,
            )
            if not results:
                typer.echo("Add cancelled — no changes made.")
            for result in results:
                render_add_receipt(result)
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
