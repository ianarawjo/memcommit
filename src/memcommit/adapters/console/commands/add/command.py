"""Typer adapter for adding exact Memories to the current Context."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.add.receipt import render_add_receipt
from memcommit.adapters.console.terminal.components.errors import render_cli_error
from memcommit.application.operations.add.application import MemAddError, AddRequest, run_add
from memcommit.application.operations.add.runtime import MemoryStoreAddTargetPort
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def require_add_memories(memories: Optional[list[str]]) -> list[str]:
    # Parse-time validation keeps missing input outside automatic Sync boundaries.
    if not memories:
        raise typer.BadParameter(
            'Example: mem add "Memory content".'
        )
    return memories


def cmd(
    memories: Annotated[
        Optional[list[str]],
        typer.Argument(
            metavar="MEMORY...",
            help="Add one Memory per positional value to the current Context; quote spaces",
            callback=require_add_memories,
        ),
    ] = None,
) -> None:
    try:
        store = MemoryStore()
        current_context_name = store.current_context_name()
        result = run_add(
            AddRequest(context_locator=None, contents=tuple(memories or ())),
            target_port=MemoryStoreAddTargetPort(
                store,
                current_context_name=current_context_name,
            ),
        )
    except (
        MemAddError,
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

    render_add_receipt(result)
