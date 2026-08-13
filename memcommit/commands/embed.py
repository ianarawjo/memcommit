from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.direct_item_placement import (
    DirectItemGap,
    direct_item_gap,
    direct_item_placement_rows,
)
from memcommit.commands.embed_dialog import (
    EmbedSetupReceipt,
    choose_embed_setup,
    embed_exact_command_review,
)
from memcommit.interfaces.console.terminal import is_interactive_terminal
from memcommit.interfaces.console.text import display_escape_text
from memcommit.context import AutoCheckpoint, Context
from memcommit.store import MemoryStore, context_record_digest


def _interactive_terminal() -> bool:
    return is_interactive_terminal()


def _resolve_gap(
    parent: Context,
    *,
    before: str | None,
    after: str | None,
) -> DirectItemGap:
    """Resolve one CLI anchor to an exact gap in the loaded target order."""

    if before is not None and after is not None:
        raise ValueError("Pass only one of --before or --after.")
    rows = direct_item_placement_rows(parent)
    if before is None and after is None:
        return direct_item_gap(rows, len(rows))
    selector = before if before is not None else after
    assert selector is not None
    anchor = ops.resolve(parent, selector)
    ordered_uids = parent.ordered_uids()
    position = ordered_uids.index(anchor.uid) + (1 if after is not None else 0)
    return direct_item_gap(rows, position)


def _gap_description(gap: DirectItemGap) -> str:
    if gap.previous_uid is not None and gap.next_uid is not None:
        return f"between [{gap.previous_uid[:8]}] and [{gap.next_uid[:8]}]"
    if gap.next_uid is not None:
        return f"before [{gap.next_uid[:8]}] at the start"
    if gap.previous_uid is not None:
        return f"after [{gap.previous_uid[:8]}] at the end"
    return "as the only direct item"


def _placement_selectors(gap: DirectItemGap) -> tuple[str | None, str | None]:
    """Use the same stable anchor that the interactive exact command displays."""

    if gap.next_uid is not None:
        return gap.next_uid, None
    if gap.previous_uid is not None:
        return None, gap.previous_uid
    return None, None


def cmd(
    a: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Context to embed; omit with all options in a terminal to choose "
                "the Child, target, and insertion gap"
            )
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option("--into", help="Target Context whose direct order changes"),
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
    if before is not None and after is not None:
        typer.secho(
            "Error: pass only one of --before or --after.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    interactive_receipt: EmbedSetupReceipt | None = None
    if a is None:
        if into is not None or before is not None or after is not None:
            typer.secho(
                "Error: run 'mem embed' with no operands for interactive setup, "
                "or pass CHILD together with --into.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        if not _interactive_terminal():
            typer.secho(
                "Error: CHILD and --into are required outside a terminal; "
                "for example: mem embed CHILD --into CONTEXT.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            interactive_receipt = choose_embed_setup(store)
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if interactive_receipt is None:
            typer.echo("Embed cancelled — no Context was changed.")
            return
        child_name = interactive_receipt.child_name
        parent_name = interactive_receipt.into_name
        before, after = _placement_selectors(interactive_receipt.gap)
    else:
        if into is None:
            typer.secho(
                "Error: --into is required when CHILD is supplied.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        try:
            child_name = snapshot.resolve(a)
            parent_name = snapshot.resolve(into)
        except ValueError as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    try:
        for name in (child_name, parent_name):
            if not store.context_exists(name):
                raise FileNotFoundError(f"Context '{name}' does not exist.")
        child = store.load_direct(child_name)
        parent = store.load_for_update(parent_name)
        if interactive_receipt is not None:
            if (
                child.uid != interactive_receipt.child_uid
                or context_record_digest(child) != interactive_receipt.child_digest
            ):
                raise RuntimeError(
                    "The Child Context changed after the exact Embed command "
                    "was reviewed."
                )
            if (
                parent.uid != interactive_receipt.into_uid
                or context_record_digest(parent) != interactive_receipt.into_digest
            ):
                raise RuntimeError(
                    "The Into Context or its direct-item order changed after "
                    "the insertion gap was reviewed."
                )
        gap = _resolve_gap(parent, before=before, after=after)
        if interactive_receipt is not None:
            if gap != interactive_receipt.gap:
                raise RuntimeError(
                    "The reviewed Embed insertion gap no longer resolves to "
                    "the same direct-item neighbors."
                )
            rebuilt_review = embed_exact_command_review(
                child_name,
                parent_name,
                gap,
                item_count=len(parent.ordered_uids()),
            )
            if rebuilt_review != interactive_receipt.review:
                raise RuntimeError(
                    "The reviewed exact Embed command changed before application."
                )
        if interactive_receipt is None and before is None and after is None:
            # Preserve the long-standing two-argument in-memory adapter path
            # for callers that intentionally request the compatibility append.
            ops.embed(child, parent)
        else:
            ops.embed(child, parent, position=gap.position)
        store.save_context_with_sources(
            parent,
            AutoCheckpoint(
                command="embed",
                args={
                    "child": child_name,
                    "into": parent_name,
                    "position": gap.position,
                    "after_uid": gap.previous_uid,
                    "before_uid": gap.next_uid,
                },
                description=(
                    f"Embedded '{child_name}' into '{parent_name}' "
                    f"{_gap_description(gap)}"
                ),
            ),
            expected_context_digest=parent._store_digest or "",
            source_bindings=(
                (child_name, child.uid, context_record_digest(child)),
            ),
        )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Embedded '{display_escape_text(child_name)}' into "
        f"'{display_escape_text(parent_name)}' {_gap_description(gap)}.",
        fg=typer.colors.GREEN,
    )
