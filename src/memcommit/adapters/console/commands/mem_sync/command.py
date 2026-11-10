"""Document Sync and Profile-local automatic scheduling controls."""

from enum import Enum
from typing import Optional

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


class AutomaticMode(str, Enum):
    on = "on"
    off = "off"
    status = "status"


def cmd(
    automatic: Optional[AutomaticMode] = typer.Option(
        None, "--auto", help="Enable, disable, or inspect automatic Sync for this Profile."
    ),
) -> None:
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
        store = ProfileStore(create=automatic != AutomaticMode.status)
        if automatic is not None:
            from memcommit.adapters.background.automatic_sync import ensure_worker, worker_is_running
            from memcommit.adapters.console.terminal.core.output import echo_text
            from memcommit.application.operations.import_export_sync.mem_sync.automatic.runtime import (
                configure_automatic_sync, synchronize_automatically,
            )
            from memcommit.persistence.operations.mem_sync.automatic import (
                read_automatic_record, read_automatic_settings,
            )

            if automatic == AutomaticMode.status:
                settings = read_automatic_settings(store)
                typer.echo(f"Automatic sync: {'on' if settings.enabled else 'off'}")
                if settings.enabled:
                    typer.echo(f"Watcher: {'running' if worker_is_running(store) else 'stopped (run mem sync --auto on to restart)'}")
                    status = read_automatic_record(store, "automatic-status.json") or {}
                    echo_text("Last check: {state}", state=status.get("state", "waiting"))
                    if status.get("message"):
                        echo_text("{message}", message=status["message"])
            elif automatic == AutomaticMode.off:
                configure_automatic_sync(store, False)
                typer.echo("Automatic sync disabled for this Profile.")
            else:
                configure_automatic_sync(store, True)
                outcome = synchronize_automatically(store, trigger="ENABLED")
                ensure_worker(store)
                typer.echo("Automatic sync enabled for this Profile. Markdown edits and mem actions now synchronize automatically.")
                if outcome.message:
                    echo_text("Automatic sync pending: {message}", message=outcome.message, err=True)
            return
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
