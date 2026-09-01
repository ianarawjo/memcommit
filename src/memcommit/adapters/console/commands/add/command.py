"""Typer adapter for adding one or more exact Memories."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from memcommit.application.operations.add.application import (
    AddError,
    AddRequest,
    AddSource,
    prepare_add_target,
    run_add,
)
from memcommit.application.operations.add.runtime import MemoryStoreAddTargetPort
from memcommit.adapters.console.commands.add.line_input_records import (
    parse_line_input_records,
)
from memcommit.adapters.console.commands.add.receipt import render_add_receipt
from memcommit.adapters.console.coordination.batch_input_source import (
    read_batch_input_text,
)
from memcommit.adapters.console.terminal.components.errors import render_cli_error
from memcommit.adapters.console.terminal.core.capabilities import is_interactive_terminal
from memcommit.adapters.console.terminal.components.paste_input import (
    PasteCancelled,
    capture_paste,
)
from memcommit.adapters.console.commands.add.workbench import (
    build_add_workbench_setup,
    run_add_workbench,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def cmd(
    info: Annotated[
        Optional[str],
        typer.Argument(help="One Memory to store (quote multi-word text)"),
    ] = None,
    input_source: Annotated[
        Optional[str],
        typer.Option(
            "--input",
            "-i",
            help="Add each non-empty line from a UTF-8 file; use '-' for stdin",
        ),
    ] = None,
    paste: Annotated[
        bool,
        typer.Option(
            "--paste",
            help=(
                "Capture pasted text without echoing it, then add each non-empty line"
            ),
        ),
    ] = False,
    memories: Annotated[
        Optional[list[str]],
        typer.Option(
            "--memory",
            "-m",
            help="Add one exact Memory; repeat the option to add a batch",
        ),
    ] = None,
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
    source_count = sum(
        (
            info is not None,
            input_source is not None,
            paste,
            bool(explicit_memories),
        )
    )
    if source_count > 1 or (source_count == 0 and not is_interactive_terminal()):
        typer.secho(
            "Error: provide exactly one of INFO, --input, or --paste, or use "
            "repeatable --memory.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    # Capture global navigation once before file, stdin, or paste intake can
    # yield control. Relative target meaning stays stable for this command.
    store = MemoryStore()
    current_name = store.current_context_name()
    port = MemoryStoreAddTargetPort(store, current_name=current_name)

    try:
        if source_count == 0:
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
            render_add_receipt(workbench_result, mode="TUI_DRAFTS")
            return
        if info is not None:
            request = AddRequest(
                context_locator=requested_context,
                contents=(info,),
                source=AddSource(
                    mode="SINGLE",
                    kind="argument",
                    raw_text=info,
                    parser="single-memory-v1",
                ),
            )
        elif explicit_memories:
            request = AddRequest(
                context_locator=requested_context,
                contents=explicit_memories,
                source=AddSource(
                    mode="EXPLICIT_BATCH",
                    kind="arguments",
                    raw_text=json.dumps(
                        explicit_memories,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    parser="explicit-memory-arguments-v1",
                ),
            )
        elif paste:
            frozen_target = prepare_add_target(
                requested_context,
                target_port=port,
            )
            try:
                raw_text = capture_paste()
            except PasteCancelled:
                typer.echo("Aborted — no changes made.")
                return
            contents = tuple(parse_line_input_records(raw_text))
            count = len(contents)
            noun = "line" if count == 1 else "lines"
            typer.secho(f"[{count} {noun} pasted]", dim=True)
            # The explicit paste mode plus its F2/Ctrl-D finish action is the
            # approval boundary; the resulting Add remains one Undo unit.
            request = AddRequest(
                context_locator=requested_context,
                contents=contents,
                source=AddSource(
                    mode="PASTE",
                    kind="interactive-paste",
                    raw_text=raw_text,
                    parser="stripped-nonempty-physical-lines-v1",
                ),
            )
        else:
            assert input_source is not None
            raw_text = read_batch_input_text(input_source)
            request = AddRequest(
                context_locator=requested_context,
                contents=tuple(parse_line_input_records(raw_text)),
                source=AddSource(
                    mode="LINES",
                    kind="stdin" if input_source == "-" else "utf-8-file",
                    raw_text=raw_text,
                    parser="stripped-nonempty-physical-lines-v1",
                    input_name=input_source,
                ),
            )

        result = run_add(
            request,
            target_port=port,
            frozen_target=(frozen_target if paste else None),
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

    render_add_receipt(result, mode=request.source.mode)
