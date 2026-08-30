"""Console orchestration for direct-Memory Copy."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.copy.receipt import render_copy_receipt
from memcommit.adapters.console.commands.copy.setup import choose_copy_setup
from memcommit.adapters.console.terminal.components.errors import render_cli_error
from memcommit.adapters.console.coordination.copy_and_move.arguments import (
    selected_memory_locators,
    target_context_option,
)
from memcommit.adapters.console.terminal.core.capabilities import is_interactive_terminal
from memcommit.application.capabilities.authority.write_protection import (
    WriteProtectionError,
)
from memcommit.application.operations.copy_and_move.application import (
    CopyMemoriesRequest,
    MemoryTransferError,
)
from memcommit.application.operations.copy.application import run_copy
from memcommit.application.operations.copy.runtime import MemoryStoreCopyPort
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def cmd(
    memory_locators: Annotated[
        Optional[list[str]],
        typer.Argument(
            show_default=False,
            help=(
                "Direct Memory UID/prefix or CONTEXT:UID; repeat positionally "
                "for an ordered batch"
            ),
        ),
    ] = None,
    memory_options: Annotated[
        Optional[list[str]],
        typer.Option(
            "--memory",
            "-m",
            metavar="[CONTEXT:]UID",
            help="Direct Memory locator; repeat for an ordered batch",
        ),
    ] = None,
    source: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            metavar="SOURCE_CONTEXT",
            help="One Source owner applied to every unqualified Memory selector",
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            metavar="TARGET_CONTEXT",
            help="Existing local Target Context (defaults to current)",
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            metavar="TARGET_CONTEXT",
            help="Compatibility alias for --into",
        ),
    ] = None,
    before: Annotated[
        Optional[str],
        typer.Option(
            "--before",
            help="Insert the copied batch before this Target direct item",
        ),
    ] = None,
    after: Annotated[
        Optional[str],
        typer.Option(
            "--after",
            help="Insert the copied batch after this Target direct item",
        ),
    ] = None,
) -> None:
    """Copy direct Memories while preserving every Source."""

    try:
        store = MemoryStore()
        # Explicit public Source owners may resolve through the active
        # Profile's Grants. Bare UID lookup and every Target stay local.
        port = MemoryStoreCopyPort.capture(
            store,
            allow_granted_sources=True,
        )
        frozen_plan = None
        bare = not any(
            (
                memory_locators,
                memory_options,
                source,
                into,
                to,
                before,
                after,
            )
        )
        if bare:
            if not is_interactive_terminal():
                raise MemoryTransferError(
                    "Memory locators are required outside a terminal; for example: "
                    "mem copy CONTEXT:MEMORY --into TARGET."
                )
            frozen_plan = choose_copy_setup(port)
            if frozen_plan is None:
                typer.echo("Copy cancelled — no Context was changed.")
                return
            request = frozen_plan.request
        else:
            request = CopyMemoriesRequest(
                memory_locators=selected_memory_locators(
                    memory_locators,
                    memory_options,
                ),
                source_locator=source,
                into_locator=target_context_option(into, to),
                before=before,
                after=after,
            )
        result = run_copy(
            request,
            port=port,
            frozen_plan=frozen_plan,
        )
    except (
        ConcurrentContextUpdateError,
        FileNotFoundError,
        KeyError,
        MemoryTransferError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        TypeError,
        ValueError,
        WriteProtectionError,
    ) as error:
        render_cli_error(error)
        raise typer.Exit(1)
    render_copy_receipt(result)


__all__ = ["cmd"]
