from collections.abc import Sequence
from typing import Annotated, Any

import typer

from memcommit.store import MemoryStore


def render_checkpoint_rows(entries: Sequence[dict[str, Any]], limit: int | None = None) -> None:
    rows = entries[:limit] if limit is not None else entries
    for cp in rows:
        ts = cp["timestamp"][:16].replace("T", " ")
        uid_short = cp["uid"][:8]
        is_auto = cp.get("auto", False)
        command = cp.get("command") or "checkpoint"
        label = " ".join((cp.get("description") or cp.get("message") or "(no message)").split())

        if is_auto:
            typer.secho(f"  {uid_short}  {ts}  {command:<12}  {label}")
        else:
            msg = cp.get("message") or "(no message)"
            typer.secho(f"  {uid_short}  {ts}  {'checkpoint':<12}  {msg}", fg=typer.colors.CYAN, bold=True)


def cmd(
    manual: Annotated[bool, typer.Option("--manual", "-m", help="Show only manually-created checkpoints")] = False,
) -> None:
    store = MemoryStore()
    name = store.current_context_name()
    if not name:
        typer.secho("No current context. Run 'mem init <name>' first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    entries = store.list_checkpoints(name)
    if manual:
        entries = [e for e in entries if not e.get("auto", False)]

    if not entries:
        msg = "No manual checkpoints" if manual else "No checkpoints"
        typer.echo(f"{msg} for '{name}' yet.")
        return

    typer.secho(f"Log for '{name}':", bold=True)
    typer.echo()
    render_checkpoint_rows(entries)
