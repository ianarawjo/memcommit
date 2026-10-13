"""Immediate Sync CLI with scope aliases and a selected-set automatic toggle."""

from typing import Annotated, Optional
from pathlib import Path
import typer

from memcommit.application.operations.mem_sync.application import run_sync
from memcommit.application.operations.mem_sync.model import SyncRequest
from memcommit.application.operations.mem_sync.runtime import SyncRuntime
from .receipt import render_sync_receipt, render_sync_error


def cmd(
    source: Annotated[
        Optional[str],
        typer.Argument(help="Owned Context; omit for the current Context."),
    ] = None,
    recursive: Annotated[
        bool, typer.Option("-r", "--recursive", help="Include lexical descendants.")
    ] = False,
    all_contexts: Annotated[
        bool,
        typer.Option("-a", "--all", help="Select every owned Context in this Profile."),
    ] = False,
    always: Annotated[
        bool,
        typer.Option(
            "--always",
            help="Toggle automatic Sync for the selected set; a mixed set enables all.",
        ),
    ] = False,
    destination: Annotated[
        Optional[Path],
        typer.Option(
            "--to",
            help="Explicitly connect/reconnect the selection beneath this external base.",
        ),
    ] = None,
):
    try:
        result = run_sync(
            SyncRequest(
                source, recursive, all_contexts, always, destination=destination
            ),
            SyncRuntime(),
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        render_sync_error(error)
        raise typer.Exit(1) from error
    render_sync_receipt(result)
