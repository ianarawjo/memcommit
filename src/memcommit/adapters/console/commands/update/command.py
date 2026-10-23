"""Apply one instruction to the current Context and optional descendants."""

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
        str,
        typer.Argument(help="One instruction to apply to the current Context."),
    ],
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Update the current Context and its lexical descendants together.",
        ),
    ] = False,
) -> None:
    """Apply one instruction, then print the completed changes."""
    try:
        request = UpdateRequest(instruction, recursive=recursive)
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
