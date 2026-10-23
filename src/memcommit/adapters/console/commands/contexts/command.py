import typer

from memcommit.adapters.console.commands.contexts.receipt import render_contexts_receipt
from memcommit.application.operations.contexts.runtime import load_contexts_catalog
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


def cmd() -> None:
    store = MemoryStore()
    try:
        context_names, current_context_name = load_contexts_catalog(store)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_contexts_receipt(context_names, current_context_name)
