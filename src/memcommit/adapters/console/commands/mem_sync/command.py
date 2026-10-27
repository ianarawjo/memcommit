"""Manual document Sync CLI."""

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome

from memcommit.application.operations.import_export_sync.mem_sync.application import (
    run_sync,
)
from memcommit.application.operations.import_export_sync.mem_sync.model import (
    SyncCancelled,
)
from memcommit.persistence.store import ProfileStore

from .receipt import render_sync_error, render_sync_receipt
from .conflict_choice import choose_sync_conflict_version


def cmd() -> None:
    """Sync all supported documents and owned Contexts in the active Profile's
    project folder, including subfolders. Supports only .md; SKILL.md is ordinary
    Markdown. Remove only the final .md from a file's Context name.
    Normalize block separators while preserving block content.
    Invalid file or folder names stop Sync; rename them to follow Context naming rules.
    Existing exclusions and .memignore
    apply. Only concurrent different changes need a
    choice; one choice applies to every conflict in the Profile.
    """
    try:
        store = ProfileStore()
        result = run_sync(
            store,
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
