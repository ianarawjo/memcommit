"""Manual document Sync CLI."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome

from memcommit.application.operations.mem_sync.application import run_sync
from memcommit.application.operations.mem_sync.model import SyncRequest, SyncCancelled
from memcommit.application.operations.mem_sync.runtime import SyncRuntime

from .receipt import render_sync_error, render_sync_receipt
from .conflict_choice import choose_sync_conflict_version


def cmd(
    source: Annotated[
        Optional[str],
        typer.Argument(
            help="Owned Context; omit to discover and sync this Profile's project documents."
        ),
    ] = None,
    recursive: Annotated[
        bool, typer.Option("-r", "--recursive", help="Include lexical descendants.")
    ] = False,
    all_contexts: Annotated[
        bool,
        typer.Option("-a", "--all", help="Select every owned Context in this Profile."),
    ] = False,
    destination: Annotated[
        Optional[Path],
        typer.Option(
            "--to",
            help="Explicitly connect/reconnect the selection beneath this external base.",
        ),
    ] = None,
):
    """Sync this Profile's documents. Only concurrent different changes need a
    choice; one choice applies to every conflict in the Profile. Both versions
    remain as checkpoints. Undo/Redo restores the entire Sync action at once.
    """
    try:
        runtime = SyncRuntime()
        result = run_sync(
            SyncRequest(
                source,
                recursive,
                all_contexts or source is None,
                destination=destination,
                discover_documents=source is None,
            ),
            runtime,
            choose_conflict_version=choose_sync_conflict_version,
        )
    except SyncCancelled:
        annotate_command_outcome("CANCELLED")
        typer.echo("Sync cancelled; nothing changed.")
        return
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        render_sync_error(error)
        raise typer.Exit(1) from error
    if result.run_uid is None:
        annotate_command_outcome("NO_CHANGE")
    render_sync_receipt(result)
