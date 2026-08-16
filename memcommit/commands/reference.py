from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context import AutoCheckpoint, Memory
from memcommit.store import MemoryStore, context_record_digest


def cmd(
    selector: Annotated[
        str,
        typer.Argument(help="UID (or unambiguous prefix) of the source memory"),
    ],
    source_name: Annotated[
        str,
        typer.Option("--from", help="Context that directly owns the source memory"),
    ],
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help="Context to add the reference to (defaults to current)",
        ),
    ] = None,
) -> None:
    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    target_selector = into or snapshot.current_name
    target_name = target_selector
    if not target_name:
        typer.secho(
            "No current context. Pass --into or run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        source_name = snapshot.resolve(source_name)
        target_name = snapshot.resolve(target_name)
        for name in (source_name, target_name):
            if not store.context_exists(name):
                raise FileNotFoundError(f"Context '{name}' does not exist.")
        source = store.load_direct(source_name)
        target = store.load_for_update(target_name)
        item = ops.resolve(source, selector)
        if not isinstance(item, Memory):
            raise TypeError(
                f"'{selector}' is not a directly owned Memory in '{source_name}'."
            )
        ref = ops.reference_memory(item, source, target)
        store.save_context_with_sources(
            target,
            AutoCheckpoint(
                command="reference",
                args={
                    "reference_uid": ref.uid,
                    "source": source_name,
                    "memory_uid": item.uid,
                    "into": target_name,
                },
                description=(
                    f"Referenced [{item.uid[:8]}] from '{source_name}' "
                    f"as [{ref.uid[:8]}] in '{target_name}'"
                ),
            ),
            expected_context_digest=target._store_digest or "",
            source_bindings=(
                (source_name, source.uid, context_record_digest(source)),
            ),
        )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Referenced [{item.uid[:8]}] from "
        f"'{display_escape_text(source_name)}' as [{ref.uid[:8]}] in "
        f"'{display_escape_text(target_name)}'.",
        fg=typer.colors.GREEN,
    )
