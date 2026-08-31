"""Console orchestration for direct-Memory Move."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.direct_changes.move.receipt import render_move_receipt
from memcommit.adapters.console.commands.direct_changes.move.setup import choose_move_setup
from memcommit.adapters.console.terminal.components.errors import render_cli_error
from memcommit.adapters.console.coordination.copy_and_move.arguments import (
    selected_memory_locators,
    target_context_option,
)
from memcommit.adapters.console.terminal.core.capabilities import is_interactive_terminal
from memcommit.application.capabilities.authority.write_protection import (
    WriteProtectionError,
)
from memcommit.application.capabilities.memory_transfer.application import (
    MemoryTransferError,
    MoveMemoriesRequest,
)
from memcommit.application.operations.direct_changes.move.application import run_move
from memcommit.application.operations.direct_changes.move.runtime import MemoryStoreMovePort
from memcommit.application.operations.profiles.profile.config import ProfileConfigError
from memcommit.application.operations.profiles.profile.model import ProfileError
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
            help="Insert the moved batch before this Target direct item",
        ),
    ] = None,
    after: Annotated[
        Optional[str],
        typer.Option(
            "--after",
            help="Insert the moved batch after this Target direct item",
        ),
    ] = None,
    retarget_links: Annotated[
        bool,
        typer.Option(
            "--retarget-links",
            help=(
                "Compatibility spelling for the default: atomically retarget "
                "every local inbound live Memory Embed"
            ),
        ),
    ] = False,
    break_links: Annotated[
        bool,
        typer.Option(
            "--break-links",
            help="Explicitly leave inbound live Memory Embeds dangling",
        ),
    ] = False,
) -> None:
    """Move direct Memories while preserving their identities."""

    try:
        if retarget_links and break_links:
            raise MemoryTransferError(
                "Pass only one of --retarget-links or --break-links."
            )
        store = MemoryStore()
        # Move recognizes Grants only so it can explain why an authority-owned
        # public Source cannot enter this local ownership mutation.
        port = MemoryStoreMovePort.capture(
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
                retarget_links,
                break_links,
            )
        )
        if bare:
            if not is_interactive_terminal():
                raise MemoryTransferError(
                    "Memory locators are required outside a terminal; for example: "
                    "mem move CONTEXT:MEMORY --into TARGET."
                )
            frozen_plan = choose_move_setup(port)
            if frozen_plan is None:
                typer.echo("Move cancelled — no Context was changed.")
                return
            request = frozen_plan.request
        else:
            request = MoveMemoriesRequest(
                memory_locators=selected_memory_locators(
                    memory_locators,
                    memory_options,
                ),
                source_locator=source,
                into_locator=target_context_option(into, to),
                before=before,
                after=after,
                link_policy="BREAK" if break_links else "RETARGET",
            )
        result = run_move(
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
    render_move_receipt(result)


__all__ = ["cmd"]
