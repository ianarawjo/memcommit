import typer

from memcommit.adapters.console.commands.list.receipt import render_list_receipt
from memcommit.application.operations.list.runtime import (
    prepare_memory_and_child_context_lists,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ProfileStore


def cmd() -> None:
    store = ProfileStore()
    try:
        current_context_name = store.current_context_name()
        if current_context_name is None:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")

        ordered_memory_list, child_context_names = prepare_memory_and_child_context_lists(
            store, current_context_name
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_list_receipt(current_context_name, ordered_memory_list, child_context_names)
