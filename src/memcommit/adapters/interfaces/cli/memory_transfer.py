"""CLI composition and plain rendering for Memory Copy and Move."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.core.context_targeting.operands import choose_endpoint_operand
from memcommit.adapters.console.errors import render_cli_error
from memcommit.adapters.console.terminal import is_interactive_terminal
from memcommit.adapters.console.text import display_escape_text
from memcommit.adapters.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.application.operations.memory_transfer.application import (
    CopyMemoriesRequest,
    CopyMemoriesResult,
    MemoryTransferError,
    MoveMemoriesRequest,
    MoveMemoriesResult,
    run_copy,
    run_move,
)
from memcommit.application.operations.memory_transfer.runtime import MemoryStoreMemoryTransferPort
from memcommit.adapters.interfaces.tui.operations.memory_transfer import (
    choose_memory_transfer_setup,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore
from memcommit.application.authority.write_protection import WriteProtectionError


def _selected_locators(
    positional: list[str] | None,
    options: list[str] | None,
) -> tuple[str, ...]:
    positional_values = tuple(positional or ())
    option_values = tuple(options or ())
    if positional_values and option_values:
        raise MemoryTransferError(
            "Use positional MEMORY locators or repeat --memory, not both."
        )
    values = positional_values or option_values
    if not values:
        raise MemoryTransferError(
            "Provide one or more MEMORY locators, or repeat --memory."
        )
    return values


def _target_option(into: str | None, to: str | None) -> str | None:
    try:
        return choose_endpoint_operand(
            None,
            role="Target",
            options=(("--into", into), ("--to", to)),
        )
    except ValueError as error:
        raise MemoryTransferError(str(error)) from error


def _placement_text(result: CopyMemoriesResult | MoveMemoriesResult) -> str:
    placement = result.placement
    if placement.previous_uid is not None and placement.next_uid is not None:
        return (
            f"between [{placement.previous_uid[:8]}] and "
            f"[{placement.next_uid[:8]}]"
        )
    if placement.next_uid is not None:
        return f"before [{placement.next_uid[:8]}] at the start"
    if placement.previous_uid is not None:
        return f"after [{placement.previous_uid[:8]}] at the end"
    return "as the only direct item"


def render_copy_plain(result: CopyMemoriesResult) -> None:
    action = typer.style(
        "COPIED",
        fg=semantic_color_rgb(SemanticColorRole.ADD),
        bold=True,
    )
    target = display_escape_text(result.into_name)
    typer.echo(
        f"{action} · {result.count} "
        f"{'Memory' if result.count == 1 else 'Memories'} → '{target}' · "
        f"NEW UIDs · {_placement_text(result)}"
    )
    for item in result.items:
        source = display_escape_text(item.source_context_name)
        typer.echo(
            f"  '{source}' [{item.source_memory_uid[:8]}] → "
            f"[{item.into_memory_uid[:8]}]"
        )
    typer.echo(
        "Checkpoint "
        + ", ".join(
            f"'{display_escape_text(item.context_name)}' [{item.checkpoint_uid[:8]}]"
            for item in result.checkpoints
        )
        + "."
    )


def render_move_plain(result: MoveMemoriesResult) -> None:
    target = display_escape_text(result.into_name)
    typer.echo(
        f"MOVED · {result.count} "
        f"{'Memory' if result.count == 1 else 'Memories'} → '{target}' · "
        f"{result.link_policy} LINKS · {_placement_text(result)}"
    )
    remove = typer.style(
        "REMOVE",
        fg=semantic_color_rgb(SemanticColorRole.REMOVE),
        bold=True,
    )
    add = typer.style(
        "ADD",
        fg=semantic_color_rgb(SemanticColorRole.ADD),
        bold=True,
    )
    for item in result.items:
        source = display_escape_text(item.source_context_name)
        typer.echo(
            f"  {remove} '{source}' [{item.source_memory_uid[:8]}] · "
            f"{add} '{target}' [{item.into_memory_uid[:8]}]"
        )
    if result.retargeted_link_count:
        typer.echo(f"Retargeted {result.retargeted_link_count} live Memory Embed(s).")
    if result.dangling_link_count:
        typer.echo(
            f"Left {result.dangling_link_count} live Memory Embed(s) dangling "
            "as explicitly requested."
        )
    typer.echo(
        "Checkpoints "
        + ", ".join(
            f"'{display_escape_text(item.context_name)}' [{item.checkpoint_uid[:8]}]"
            for item in result.checkpoints
        )
        + "."
    )


def copy_cmd(
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
    try:
        store = MemoryStore()
        # The CLI's default Store is the active Profile, so explicit public
        # Source owners may resolve through that Profile's Grants. Bare UID
        # lookup and every Target remain ordinary-local.
        port = MemoryStoreMemoryTransferPort.capture(
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
            frozen_plan = choose_memory_transfer_setup(port, kind="COPY")
            if frozen_plan is None:
                typer.echo("Copy cancelled — no Context was changed.")
                return
            request = frozen_plan.request
        else:
            locators = _selected_locators(memory_locators, memory_options)
            target = _target_option(into, to)
            request = CopyMemoriesRequest(
                memory_locators=locators,
                source_locator=source,
                into_locator=target,
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
    render_copy_plain(result)


def move_cmd(
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
    try:
        if retarget_links and break_links:
            raise MemoryTransferError(
                "Pass only one of --retarget-links or --break-links."
            )
        store = MemoryStore()
        # Move still opts into Grant recognition so it can explain the
        # ownership boundary instead of misreporting a public Source as absent.
        port = MemoryStoreMemoryTransferPort.capture(
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
            frozen_plan = choose_memory_transfer_setup(port, kind="MOVE")
            if frozen_plan is None:
                typer.echo("Move cancelled — no Context was changed.")
                return
            request = frozen_plan.request
        else:
            locators = _selected_locators(memory_locators, memory_options)
            target = _target_option(into, to)
            request = MoveMemoriesRequest(
                memory_locators=locators,
                source_locator=source,
                into_locator=target,
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
    render_move_plain(result)


__all__ = ["copy_cmd", "move_cmd", "render_copy_plain", "render_move_plain"]
