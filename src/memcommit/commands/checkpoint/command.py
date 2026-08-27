from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Optional

import typer

from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.persistence.store import MemoryStore, context_record_digest


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
    snapshot = ContextOperandSnapshot.capture(store)
    try:
        context_name = snapshot.resolve_or_current(operands.context_locator)
        if context_name is None:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        root = store.load_direct(context_name)
        if preset is ContextScopePreset.DIRECT:
            checkpoint = store.checkpoint(root, operands.message or "")
            ts = checkpoint.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            typer.secho(
                f"[{checkpoint.uid[:8]}] {ts}  "
                f"Context '{display_escape_text(context_name)}'  "
                f"{_label(operands.message)}",
                fg=typer.colors.GREEN,
            )
            return

        catalog_names = tuple(store.list_context_names())
        context_names = expand_lexical_context_names(
            ContextScope.create(
                (context_name,),
                include_descendants=True,
            ),
            catalog_names,
        )
        contexts = tuple(
            root if name == context_name else store.load_direct(name)
            for name in context_names
        )
        membership = [
            {"uid": context.uid, "name": context.name} for context in contexts
        ]
        checkpoint_uids = tuple(str(uuid.uuid4()) for _context in contexts)
        checkpoint_uid_by_name = {
            context.name: checkpoint_uid
            for context, checkpoint_uid in zip(contexts, checkpoint_uids)
        }
        root_checkpoint_uid = checkpoint_uid_by_name[context_name]
        checkpoint_set = {
            "version": 2,
            # A recursive recovery unit must be reachable through the same
            # globally searchable identity as an ordinary checkpoint.  The
            # root's physical checkpoint is therefore the canonical handle;
            # no receipt-only UID is minted beside the checkpoint catalog.
            "uid": root_checkpoint_uid,
            "root": {"uid": root.uid, "name": root.name},
            "include_descendants": True,
            "members": [
                {
                    "context_uid": context.uid,
                    "context_name": context.name,
                    "checkpoint_uid": checkpoint_uid_by_name[context.name],
                }
                for context in contexts
            ],
        }
        checkpoints = store.checkpoint_context_batch(
            ((context, context_record_digest(context)) for context in contexts),
            message=operands.message or "",
            command="checkpoint",
            args={
                "checkpoint_set": checkpoint_set,
                "command_contexts": membership,
            },
            description=(
                operands.message
                or (
                    f"Manual checkpoint set for {len(contexts)} Context(s) "
                    f"under '{context_name}'"
                )
            ),
            expected_context_catalog=catalog_names,
            checkpoint_uids=checkpoint_uids,
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Checkpoint error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    ts = checkpoints[0].timestamp.strftime("%Y-%m-%d %H:%M:%S")
    typer.secho(
        f"[{root_checkpoint_uid[:8]}] {ts}  Checkpoint set · "
        f"{len(checkpoints)} Context(s) under "
        f"'{display_escape_text(context_name)}'  {_label(operands.message)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Revert: mem revert {root_checkpoint_uid} --keep")
