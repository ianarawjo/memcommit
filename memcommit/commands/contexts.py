import typer

from memcommit.store import MemoryStore


def cmd() -> None:
    store = MemoryStore()
    names = store.list_context_names()
    current = store.current_context_name()
    if not names:
        typer.echo("No contexts yet. Run 'mem init <name>' to create one.")
        return
    for name in names:
        if name == current:
            typer.secho(f"* {name}", fg=typer.colors.GREEN, bold=True)
        else:
            typer.echo(f"  {name}")
