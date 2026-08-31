"""Atomize one exact Context or direct-Memory target in place."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.semantic_updates.derive.atomize.receipt import (
    render_atomize_apply_result,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.adapters.console.terminal.components.progress import (
    progressing_provider_factory,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.semantic_updates.derive.atomize.application import AtomizeInPlaceRequest
from memcommit.application.operations.semantic_updates.derive.atomize.domain import AtomizeImpactError
from memcommit.application.operations.semantic_updates.derive.atomize.runtime import execute_atomize_in_place
from memcommit.application.capabilities.local_target_lookup import (
    DirectMemoryAmbiguityError,
    resolve_local_context_memory_target,
)
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryLocator,
    DirectMemoryTarget,
    ExistingContextOperand,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)


def _parse_target(
    context_operand: str | None,
    *,
    context_name: str | None,
    memory_selector: str | None,
) -> tuple[str | None, str | None]:
    """Normalize positional and explicit spellings without loading a Context."""

    parsed_operand = (
        parse_auto_typed_context_memory_operand(context_operand)
        if context_operand is not None
        else None
    )
    if (
        isinstance(parsed_operand, ExistingContextOperand)
        and context_name is None
        and is_memory_uid_prefix(context_operand)
    ):
        early_store = MemoryStore(create=False)
        early_snapshot = ContextOperandSnapshot.capture(early_store)
        try:
            early_target = resolve_local_context_memory_target(
                early_store,
                context_operand,
                current=early_snapshot.current_name,
            )
        except FileNotFoundError:
            early_target = None
        except DirectMemoryAmbiguityError:
            # Preserve the direct-Memory interpretation so the complete owner
            # ambiguity is reported before a provider can be connected.
            parsed_operand = DirectMemoryLocator(context_operand)
            early_target = None
        if isinstance(early_target, DirectMemoryTarget):
            parsed_operand = DirectMemoryLocator(
                early_target.memory_uid,
                early_target.context_name,
            )

    if isinstance(parsed_operand, DirectMemoryLocator):
        if context_name is not None:
            raise ValueError(
                "Auto-typed Memory cannot be combined with --context; use "
                "CONTEXT:UID or --context CONTEXT --memory UID."
            )
        if memory_selector is not None:
            raise ValueError("Memory was supplied both positionally and with --memory.")
        return parsed_operand.context_locator, parsed_operand.memory_selector

    positional_context = (
        parsed_operand.locator
        if isinstance(parsed_operand, ExistingContextOperand)
        else None
    )
    return (
        choose_context_operand(positional_context, option=context_name),
        memory_selector,
    )


def cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="[TARGET]",
            help=(
                "Existing Context, Memory UID/prefix, or CONTEXT:UID "
                "(defaults to current Context)"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to atomize in place (defaults to current)",
        ),
    ] = None,
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            metavar="UID_OR_PREFIX",
            help=(
                "Atomize one direct Memory; its Context neighbors are "
                "non-actionable evidence"
            ),
        ),
    ] = None,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Force a new semantic analysis before applying this target",
        ),
    ] = False,
) -> None:
    """Atomize one exact target and immediately apply it in place."""

    try:
        context_name, memory_selector = _parse_target(
            context_operand,
            context_name=context_name,
            memory_selector=memory_selector,
        )
    except ValueError as error:
        typer.secho(
            f"Atomize error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    try:
        store = MemoryStore(create=False)
        context_snapshot = ContextOperandSnapshot.capture(store)
        if context_operand is not None:
            target = resolve_local_context_memory_target(
                store,
                context_operand,
                current=context_snapshot.current_name,
            )
            if isinstance(target, DirectMemoryTarget):
                context_name = target.context_name
                memory_selector = target.memory_uid
            else:
                assert isinstance(target, ContextTarget)
                context_name = target.context_name

        canonical_name = context_snapshot.resolve_or_current(context_name)
        if not canonical_name:
            raise AtomizeImpactError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        source = store.load_direct(canonical_name)

        with progressing_provider_factory(
            "ATOMIZE",
            "analyzing and normalizing memory structure",
            connect_codex_chatgpt_provider,
        ) as provider_factory:
            executed = execute_atomize_in_place(
                AtomizeInPlaceRequest(
                    context=source,
                    memory_selector=memory_selector,
                    refresh=refresh,
                ),
                store=store,
                provider_factory=provider_factory,
            )
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        AtomizeImpactError,
        QueryProviderError,
    ) as error:
        typer.secho(
            f"Atomize error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    applied = executed.application
    render_atomize_apply_result(
        session=executed.analysis,
        context_name=applied.materialization.context_name,
        result=applied.materialization.result,
        checkpoint_uid=applied.materialization.checkpoint_uid,
        created=False,
        audit=applied.audit,
        recovered_application=applied.recovered,
        exact_prewarm=executed.analysis_origin == "EXACT_PREWARM",
    )
