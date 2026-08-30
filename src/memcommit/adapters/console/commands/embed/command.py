"""CLI composition for the Embed application use case."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.application.capabilities.authority.context_access import resolve_context_access
from memcommit.core.context_targeting.loading import (
    resolve_local_context_memory_target,
    resolve_local_direct_memory_locator,
)
from memcommit.core.context_targeting.memory_focus import is_memory_uid_prefix
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryLocator,
    DirectMemoryTarget,
)
from memcommit.core.context_targeting.operands import choose_endpoint_operand
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.application.operations.embed.application import (
    EmbedRequest,
    FrozenMemoryEmbedPlan,
    MemoryEmbedRequest,
    run_embed,
    run_memory_embed,
)
from memcommit.application.operations.embed.runtime import MemoryStoreEmbedPort
from memcommit.adapters.console.commands.embed.receipt import render_embed_plain
from memcommit.adapters.console.commands.embed.workbench import choose_embed_setup
from memcommit.adapters.console.terminal.core.capabilities import is_interactive_terminal
from memcommit.adapters.console.terminal.core.text import display_escape_text, safe_terminal_text
from memcommit.persistence.store import MemoryStore


def _interactive_terminal() -> bool:
    return is_interactive_terminal()


def cmd(
    a: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Context, unique local Memory UID/prefix, or CONTEXT:UID; "
                "omit with all options in a terminal for interactive setup"
            )
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=(
                "Source Context when ITEM is omitted; otherwise the owner "
                "Context for an explicit Memory selector"
            ),
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help="Target Context whose direct order changes (defaults to current)",
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Compatibility alias for --into",
        ),
    ] = None,
    before: Annotated[
        Optional[str],
        typer.Option(
            "--before",
            help="Insert before this direct item UID/prefix or exact pointer name",
        ),
    ] = None,
    after: Annotated[
        Optional[str],
        typer.Option(
            "--after",
            help="Insert after this direct item UID/prefix or exact pointer name",
        ),
    ] = None,
) -> None:
    try:
        target_option = choose_endpoint_operand(
            None,
            role="Target",
            options=(("--into", into), ("--to", to)),
        )
    except ValueError as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    if before is not None and after is not None:
        typer.secho(
            "Error: pass only one of --before or --after.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore()
    # The CLI runs in the active Profile and may therefore resolve its reviewed
    # public Grant namespace. Explicit-root library clients opt in separately.
    port = MemoryStoreEmbedPort.capture(store, allow_granted_sources=True)
    frozen_plan = None
    source_from_option = a is None and source_name is not None
    source_item = source_name if source_from_option else a
    memory_owner = None if source_from_option else source_name
    if source_item is None:
        if target_option is not None or before is not None or after is not None:
            typer.secho(
                "Error: run 'mem embed' with no operands for interactive setup, "
                "or pass an item for the non-interactive form.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        if not _interactive_terminal():
            typer.secho(
                "Error: an item is required outside a terminal; for example: "
                "mem embed CHILD, mem embed MEMORY, or mem embed CONTEXT:MEMORY. "
                "Pass --into to override the current Target Context.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            frozen_plan = choose_embed_setup(port)
        except (
            FileNotFoundError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if frozen_plan is None:
            typer.echo("Embed cancelled — no Context was changed.")
            return
        request = frozen_plan.request
    else:
        target_locator = target_option or port.current_context_name
        if target_locator is None:
            typer.secho(
                "Error: no current Context. Pass --into (or --to) or initialize "
                "a Context first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            parsed_source = (
                parse_auto_typed_context_memory_operand(
                    source_item,
                    explicit_memory_context=memory_owner,
                )
                if not source_from_option
                else None
            )
            auto_target = None
            if parsed_source is not None and not isinstance(
                parsed_source, DirectMemoryLocator
            ):
                exact_access = None
                if is_memory_uid_prefix(source_item):
                    try:
                        exact_access = resolve_context_access(
                            port.store,
                            source_item,
                            current_name=port.current_context_name,
                            required_permission="EMBED",
                        )
                    except FileNotFoundError:
                        pass
                if exact_access is not None:
                    auto_target = ContextTarget(exact_access.display_name)
                else:
                    try:
                        auto_target = resolve_local_context_memory_target(
                            port.store,
                            source_item,
                            current=port.current_context_name,
                        )
                    except FileNotFoundError:
                        # A missing local Context may still be a granted public
                        # Context. Keep that operation-owned authority route when
                        # no short local Memory matched.
                        auto_target = None
            if isinstance(parsed_source, DirectMemoryLocator) or isinstance(
                auto_target,
                DirectMemoryTarget,
            ):
                granted_memory_source = None
                if (
                    isinstance(parsed_source, DirectMemoryLocator)
                    and parsed_source.context_locator is not None
                ):
                    access = resolve_context_access(
                        port.store,
                        parsed_source.context_locator,
                        current_name=port.current_context_name,
                        required_permission="EMBED",
                    )
                    if access.is_granted:
                        # An explicit public owner is the only Grant-aware
                        # Memory form. Bare UID lookup remains a complete,
                        # unambiguous ordinary-local scan and never enumerates
                        # authority content merely to guess an owner.
                        granted_memory_source = DirectMemoryTarget(
                            access.display_name,
                            parsed_source.memory_selector,
                        )
                memory_target = granted_memory_source or (
                    resolve_local_direct_memory_locator(
                        port.store,
                        (
                            source_item
                            if isinstance(parsed_source, DirectMemoryLocator)
                            else auto_target.memory_uid
                        ),
                        current=port.current_context_name,
                        explicit_context=(
                            memory_owner
                            if isinstance(parsed_source, DirectMemoryLocator)
                            else auto_target.context_name
                        ),
                    )
                )
                request = MemoryEmbedRequest(
                    memory_selector=memory_target.memory_uid,
                    source_locator=memory_target.context_name,
                    into_locator=target_locator,
                    before=before,
                    after=after,
                )
            else:
                request = EmbedRequest(
                    child_locator=(
                        auto_target.context_name
                        if auto_target is not None
                        else source_item
                    ),
                    into_locator=target_locator,
                    before=before,
                    after=after,
                )
        except (
            FileNotFoundError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Error: {safe_terminal_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    try:
        if isinstance(request, MemoryEmbedRequest):
            result = run_memory_embed(
                request,
                port=port,
                frozen_plan=(
                    frozen_plan
                    if isinstance(frozen_plan, FrozenMemoryEmbedPlan)
                    else None
                ),
            )
        else:
            result = run_embed(
                request,
                port=port,
                frozen_plan=frozen_plan,
            )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    render_embed_plain(result)
