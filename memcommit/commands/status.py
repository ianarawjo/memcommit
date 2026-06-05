import typer

from memcommit.context import Context, Memory
from memcommit.commands.log import render_checkpoint_rows
from memcommit.store import MemoryStore


def cmd() -> None:
    store = MemoryStore()
    name = store.current_context_name()
    if not name:
        typer.secho("No current context. Run 'mem init <name>' to get started.", fg=typer.colors.YELLOW)
        return

    ctx = store.load(name)
    memories = [v for v in ctx.memories.values() if isinstance(v, Memory)]
    embedded = [v for v in ctx.memories.values() if isinstance(v, Context)]
    checkpoints = store.list_checkpoints(name)

    typer.secho(f"On context: {name}", bold=True)
    typer.echo(
        f"  {len(memories)} memor{'y' if len(memories) == 1 else 'ies'}"
        f"  |  {len(embedded)} embedded context{'s' if len(embedded) != 1 else ''}"
        f"  |  {len(checkpoints)} checkpoint{'s' if len(checkpoints) != 1 else ''}"
    )

    if embedded:
        typer.secho("\nEmbedded contexts:", bold=True)
        for ec in embedded:
            typer.echo(f"  [{ec.uid[:8]}] {ec.name}")

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
