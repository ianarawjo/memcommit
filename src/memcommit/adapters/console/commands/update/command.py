"""Apply one explicit instruction to the current or named Target Context."""

import os
import sys
from typing import Annotated

import typer

from memcommit.adapters.console.commands.update.receipt import render_update_receipt
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.adapters.console.terminal.core.output import echo_text
from memcommit.application.operations.update.instruction import run_instruction_update
from memcommit.application.operations.update.model.instruction import UpdateRequest
from memcommit.persistence.store import MemoryStore
from memcommit.providers.connection import connect_semantic_provider


def cmd(
    instruction: Annotated[
        str | None,
        typer.Argument(help="One instruction to apply to the Target Context."),
    ] = None,
    memory: Annotated[
        str | None,
        typer.Option(
            "--memory",
            "-m",
            metavar="UID_OR_CONTEXT:UID",
            help="Use one stored Memory outside the Target as the instruction.",
        ),
    ] = None,
    target_name: Annotated[
        str | None,
        typer.Option(
            "--to",
            metavar="CONTEXT",
            help="Target Context (defaults to current; direct contents only).",
        ),
    ] = None,
) -> None:
    """Apply one instruction or --memory UID, then print the completed changes."""
    try:
        request = UpdateRequest(instruction, memory, target_name)
    except (ValueError, RuntimeError) as error:
        echo_text("Update error: {error}", error=error, err=True)
        raise typer.Exit(2) from error

    try:

        def execute(progress):
            def connect():
                progress.update("planning changes", step=1)
                return connect_semantic_provider()

            return run_instruction_update(MemoryStore(), request, connect)

        receipt = run_command_wait(
            "UPDATE", "preparing instruction", total=2, work=execute
        )
    except (OSError, ValueError, RuntimeError) as error:
        echo_text("Update error: {error}", error=error, err=True)
        raise typer.Exit(1) from error
    typer.echo(
        render_update_receipt(
            receipt, color=sys.stdout.isatty() and "NO_COLOR" not in os.environ
        )
    )
