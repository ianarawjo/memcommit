from typing import Annotated, Optional

import typer

from memcommit.store import MemoryStore


def cmd(
    message: Annotated[Optional[str], typer.Argument(help="Optional message describing this checkpoint")] = None,
) -> None:
    store = MemoryStore()
    try:
        ctx = store.load_current_direct()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    cp = store.checkpoint(ctx, message or "")
    ts = cp.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    label = f"'{message}'" if message else "(no message)"
    typer.secho(f"[{cp.uid[:8]}] {ts}  {label}", fg=typer.colors.GREEN)
