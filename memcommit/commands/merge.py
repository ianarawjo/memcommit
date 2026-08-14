"""Typer adapter for structural Context Merge."""

from typing import Annotated, Optional

import typer

from memcommit.interfaces.cli.merge import render_merge_plain
from memcommit.interfaces.console.terminal import is_interactive_terminal
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.merge import (
    build_merge_tui_setup,
    run_merge_tui,
)
from memcommit.merge_application import (
    MergeError,
    MergeReach,
    MergeRequest,
    run_merge,
)
from memcommit.merge_runtime import MemoryStoreMergePort
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def cmd(
    source: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Readable Source Context to structurally merge into the frozen "
                "current Target; omit in a TTY to choose it interactively"
            )
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Merge direct items from the exact Source root only (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Merge matching lexical descendants by complete relative path, "
                "creating Source-only Target paths"
            ),
        ),
    ] = False,
) -> None:
    if direct and recursive:
        typer.secho(
            "Error: choose either --direct or --recursive, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore()
    current = store.current_context_name()
    if not current:
        typer.secho(
            "No current context. Run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    port = MemoryStoreMergePort(store, current_name=current)
    try:
        if source is None:
            if not is_interactive_terminal():
                raise MergeError(
                    "Merge requires SOURCE outside a TTY; pass SOURCE with "
                    "--direct or --recursive."
                )
            setup = build_merge_tui_setup(
                port,
                initial_recursive=recursive,
            )
            result = run_merge_tui(
                setup=setup,
                execute=lambda request: run_merge(request, port=port),
            )
            if result is None:
                typer.echo("Merge cancelled — no changes made.")
                return
        else:
            result = run_merge(
                MergeRequest(
                    source_locator=source,
                    reach=(MergeReach.DESCENDANTS if recursive else MergeReach.DIRECT),
                ),
                port=port,
            )
    except (
        FileNotFoundError,
        MergeError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    render_merge_plain(result)
