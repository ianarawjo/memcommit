from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.checkpoint.application import CheckpointRequest
from memcommit.application.operations.checkpoint.runtime import execute_checkpoint
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class _CheckpointOperands:
    context_locator: str | None
    message: str | None


def _resolve_checkpoint_operands(
    first: str | None,
    second: str | None,
    *,
    context_option: str | None,
    message_option: str | None,
) -> _CheckpointOperands:
    """Resolve the compatibility grammar without consulting mutable state.

    One positional operand remains the historical message form. Two positional
    operands make the first Context role explicit. Either named option also
    disambiguates the remaining positional operand as the other role.
    """

    if context_option is not None and message_option is not None:
        if first is not None or second is not None:
            raise ValueError(
                "Positional operands cannot be combined when both --context "
                "and --message are supplied."
            )
        return _CheckpointOperands(context_option, message_option)

    if second is not None:
        if context_option is not None:
            raise ValueError(
                "CONTEXT cannot be supplied both positionally and with --context."
            )
        if message_option is not None:
            raise ValueError(
                "MESSAGE cannot be supplied both positionally and with --message."
            )
        return _CheckpointOperands(first, second)

    if context_option is not None:
        return _CheckpointOperands(context_option, first)
    if message_option is not None:
        return _CheckpointOperands(first, message_option)
    return _CheckpointOperands(None, first)


def _label(message: str | None) -> str:
    return f"'{display_escape_text(message)}'" if message else "(no message)"


def cmd(
    context_or_message: Annotated[
        Optional[str],
        typer.Argument(
            metavar="CONTEXT_OR_MESSAGE",
            help=(
                "Message for the current Context, or an existing Context locator "
                "when followed by MESSAGE or paired with --message"
            ),
        ),
    ] = None,
    message: Annotated[
        Optional[str],
        typer.Argument(
            metavar="MESSAGE",
            help="Message when the first positional operand is a Context",
        ),
    ] = None,
    context_option: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            metavar="CONTEXT",
            help="Existing local Context; omit to use the current Context",
        ),
    ] = None,
    message_option: Annotated[
        Optional[str],
        typer.Option(
            "--message",
            "-m",
            help="Optional message describing this checkpoint",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Checkpoint only the selected Context (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Checkpoint the selected local Context and every lexical "
                "descendant as one atomic set"
            ),
        ),
    ] = False,
) -> None:
    try:
        operands = _resolve_checkpoint_operands(
            context_or_message,
            message,
            context_option=context_option,
            message_option=message_option,
        )
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except ValueError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    store = MemoryStore()
    try:
        snapshot = ContextOperandSnapshot.capture(store)
        result = execute_checkpoint(
            store,
            CheckpointRequest(
                context_locator=operands.context_locator,
                current_context_name=snapshot.current_name,
                message=operands.message or "",
                recursive=preset is ContextScopePreset.RECURSIVE,
            ),
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Checkpoint error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    ts = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    if not result.recursive:
        typer.secho(
            f"[{result.root_checkpoint_uid[:8]}] {ts}  "
            f"Context '{display_escape_text(result.root_context_name)}'  "
            f"{_label(result.message)}",
            fg=typer.colors.GREEN,
        )
        return
    typer.secho(
        f"[{result.root_checkpoint_uid[:8]}] {ts}  Checkpoint set · "
        f"{result.member_count} Context(s) under "
        f"'{display_escape_text(result.root_context_name)}'  "
        f"{_label(result.message)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Revert: mem revert {result.root_checkpoint_uid} --keep")
