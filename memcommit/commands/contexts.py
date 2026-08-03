import typer

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.store import MemoryStore


def cmd() -> None:
    store = MemoryStore()
    # The marker and catalog are one read-only view of the active name captured
    # at command entry; another process may switch after this snapshot.
    current = store.current_context_name()
    names = store.list_context_names()
    if not names:
        typer.echo("No contexts yet. Run 'mem init <name>' to create one.")
        return
    for name in names:
        label = display_escape_text(name)
        if name == current:
            typer.secho(f"* {label}", fg=typer.colors.GREEN, bold=True)
        else:
            typer.echo(f"  {label}")
