import typer

from memcommit.context import Context, Memory, MemoryRef
from memcommit.commands.log import render_checkpoint_rows
from memcommit.store import MemoryStore


def cmd() -> None:
    store = MemoryStore()
    name = store.current_context_name()
    if not name:
        typer.secho("No current context. Run 'mem init <name>' to get started.", fg=typer.colors.YELLOW)
        return

    ctx = store.load(name)
    items = list(ctx.iter_items())
    memories = [v for v in items if isinstance(v, Memory)]
    references = [v for v in items if isinstance(v, MemoryRef)]
    embedded = [v for v in items if isinstance(v, Context)]
    checkpoints = store.list_checkpoints(name)

    typer.secho(f"On context: {name}", bold=True)
    typer.echo(
        f"  {len(memories)} memor{'y' if len(memories) == 1 else 'ies'}"
        f"  |  {len(references)} memory reference{'s' if len(references) != 1 else ''}"
        f"  |  {len(embedded)} embedded context{'s' if len(embedded) != 1 else ''}"
        f"  |  {len(checkpoints)} checkpoint{'s' if len(checkpoints) != 1 else ''}"
    )

    if embedded:
        typer.secho("\nEmbedded contexts:", bold=True)
        for ec in embedded:
            typer.echo(f"  [{ec.uid[:8]}] {ec.name}")

    if references:
        typer.secho("\nMemory references:", bold=True)
        for ref in references:
            state = "" if ref.is_resolved else " (dangling)"
            typer.echo(
                f"  [{ref.uid[:8]}] "
                f"{ref.target_context_name}#{ref.target_memory_uid[:8]}{state}"
            )

    if memories:
        typer.secho("\nRecent memories:", bold=True)
        for mem in memories[-5:]:
            typer.echo(f"  [{mem.uid[:8]}] ", nl=False)
            lines = mem.content.splitlines()
            preview = "\n         ".join(lines[:5])
            suffix = "\n         …" if len(lines) > 5 else ""
            typer.secho(f"{preview}{suffix}", dim=True)
    else:
        typer.echo("\n  (no memories yet)")

    if checkpoints:
        typer.secho("\nRecent checkpoints:", bold=True)
        render_checkpoint_rows(checkpoints, limit=5)
    else:
        typer.echo("\n  (no checkpoints yet)")
