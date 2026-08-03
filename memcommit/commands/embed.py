from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.context import AutoCheckpoint
from memcommit.store import MemoryStore, context_record_digest


def cmd(
    a: Annotated[str, typer.Argument(help="Context to embed")],
    into: Annotated[str, typer.Option("--into", help="Target context to embed into")],
) -> None:
    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    try:
        child_name = snapshot.resolve(a)
        parent_name = snapshot.resolve(into)
        for name in (child_name, parent_name):
            if not store.context_exists(name):
                raise FileNotFoundError(f"Context '{name}' does not exist.")
        child = store.load_direct(child_name)
        parent = store.load_for_update(parent_name)
        ops.embed(child, parent)
        store.save_context_with_sources(
            parent,
            AutoCheckpoint(
                command="embed",
                args={"child": child_name, "into": parent_name},
                description=f"Embedded '{child_name}' into '{parent_name}'",
            ),
            expected_context_digest=parent._store_digest or "",
            source_bindings=(
                (child_name, child.uid, context_record_digest(child)),
            ),
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Embedded '{display_escape_text(child_name)}' into "
        f"'{display_escape_text(parent_name)}'.",
        fg=typer.colors.GREEN,
    )
