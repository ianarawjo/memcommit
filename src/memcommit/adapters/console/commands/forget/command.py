"""Forget keywords or described content in the current Context."""

import os
import sys
from typing import Annotated

from click import UsageError
import typer

from memcommit.adapters.console.commands.update.receipt import render_update_receipt
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.adapters.console.terminal.core.output import echo_text
from memcommit.application.operations.forget.application import run_forget
from memcommit.persistence.store import ProfileStore
from memcommit.providers.connection import connect_semantic_provider


def cmd(
    content: Annotated[
        str | None,
        typer.Argument(
            metavar="KEYWORDS OR CONTENT TO FORGET",
            show_default=False,
            help="Keywords or a description of information to forget in the current Context.",
        ),
    ] = None,
) -> None:
    """Apply the planned edits and removals, then print their receipt."""
    if content is None or not content.strip():
        raise UsageError(
            'Missing required input. Example: mem forget "KEYWORDS OR CONTENT TO FORGET".'
        )
    try:

        def execute(progress):
            def connect():
                progress.update("planning changes", step=1)
                return connect_semantic_provider()

            return run_forget(ProfileStore(), content, connect)

        receipt = run_command_wait(
            "FORGET", "preparing instruction", total=2, work=execute
        )
    except (OSError, ValueError, RuntimeError) as error:
        echo_text("Forget error: {error}", error=error, err=True)
        raise typer.Exit(1) from error
    typer.echo(
        render_update_receipt(
            receipt,
            color=sys.stdout.isatty() and "NO_COLOR" not in os.environ,
            command_label="FORGET",
            instruction_text=content,
        )
    )
