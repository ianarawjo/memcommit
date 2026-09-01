"""Typer adapter for adding one or more exact Memories."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from memcommit.application.operations.add.application import (
    AddError,
    AddRequest,
    AddSource,
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
    is_interactive_terminal,
)
from memcommit.adapters.console.commands.add.workbench import (
    build_add_workbench_setup,
    run_add_workbench,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


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
    requested_context: Annotated[
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
    explicit_memories = tuple(memories or ())
    if explicit_memories and paste:
        typer.secho(
            "Error: provide positional MEMORY values or --paste, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    has_direct_source = bool(explicit_memories) or paste
    if not has_direct_source and not is_interactive_terminal():
        typer.secho(
            "Error: provide one or more positional MEMORY values, or use --paste.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    # Capture global navigation once before clipboard or workbench intake can
    # yield control. Relative target meaning stays stable for this command.
    store = MemoryStore()
    current_name = store.current_context_name()
    port = MemoryStoreAddTargetPort(store, current_name=current_name)

    try:
        if not has_direct_source:
            setup = build_add_workbench_setup(
                store,
                current_name=current_name,
                requested_context=requested_context,
            )
            workbench_result = run_add_workbench(
                setup=setup,
                execute=lambda request: run_add(request, target_port=port),
            )
            if workbench_result is None:
                typer.echo("Add cancelled — no changes made.")
                return
            render_add_receipt(workbench_result)
            return
        if explicit_memories:
            single = len(explicit_memories) == 1
            request = AddRequest(
                context_locator=requested_context,
                contents=explicit_memories,
                source=AddSource(
                    mode="SINGLE" if single else "EXPLICIT_BATCH",
                    kind="argument" if single else "arguments",
                    raw_text=(
                        explicit_memories[0]
                        if single
                        else json.dumps(
                            explicit_memories,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    ),
                    parser=(
                        "single-memory-v1" if single else "explicit-memory-arguments-v1"
                    ),
                ),
            )
        elif paste:
            raw_text = read_system_clipboard()
            contents = parse_line_input_records(raw_text)
            request = AddRequest(
                context_locator=requested_context,
                contents=contents,
                source=AddSource(
                    mode="PASTE",
                    kind="system-clipboard",
                    raw_text=raw_text,
                    parser="stripped-nonempty-physical-lines-v1",
                ),
            )
        result = run_add(
            request,
            target_port=port,
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
