import typer

from memcommit.store import MemoryStore


def cmd() -> None:
    store = MemoryStore()
    name = store.current_context_name()
    if not name:
        typer.secho("No current context. Run 'mem init <name>' first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    entries = store.list_checkpoints(name)
    if not entries:
        typer.echo(f"No checkpoints for '{name}' yet.")
        return
    typer.secho(f"Checkpoints for '{name}':", bold=True)
    for cp in entries:
        ts = cp["timestamp"][:19].replace("T", " ")
        msg = cp["message"] or "(no message)"
        typer.echo(f"  {cp['uid'][:8]}  {ts}  {msg}")
