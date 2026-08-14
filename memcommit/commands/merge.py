"""Typer adapter for structural Context Merge."""

from typing import Annotated

import typer

from memcommit.interfaces.cli.merge import render_merge_plain
from memcommit.interfaces.console.text import display_escape_text
from memcommit.merge_application import MergeError, MergeRequest, run_merge
from memcommit.merge_runtime import MemoryStoreMergePort
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def cmd(
    other: Annotated[
        str, typer.Argument(help="Name of the context to merge into the current one")
    ],
) -> None:
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
        result = run_merge(MergeRequest(source_locator=other), port=port)
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
