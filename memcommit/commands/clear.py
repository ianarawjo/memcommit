from typing import Annotated, Optional

import typer

from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import (
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.context import AutoCheckpoint
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def cmd(
    context_name: Annotated[Optional[str], typer.Argument(help="Context to clear (defaults to current)")] = None,
    force: Annotated[bool, typer.Option("-f", "--force", help="Skip confirmation prompt")] = False,
) -> None:
    active_store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(active_store)
    try:
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=snapshot.current_name,
            required_permission="DELETE",
        )
        store = access.store
        ctx = store.load_direct(access.context_name)
        context_name = access.display_name
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    display_name = display_escape_text(context_name)
    count = len(ctx.memories)

    if count == 0:
        typer.secho(
            f"Context '{display_name}' is already empty.",
            fg=typer.colors.YELLOW,
        )
        return

    if not force:
        typer.echo(f"This will remove all {count} item(s) from '{display_name}'.")
        typer.confirm("Continue?", abort=True)

    ctx.clear()
    try:
        with authorized_context_mutation(
            access,
            required_permissions=("DELETE",),
        ):
            store.save(ctx, AutoCheckpoint(
                command="clear",
                args={
                    "count": count,
                    "context": context_name,
                    **grant_checkpoint_args(access),
                },
                description=f"Cleared all {count} item(s) from '{context_name}'",
            ))
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.secho(
        f"Cleared {count} item(s) from '{display_name}'.",
        fg=typer.colors.GREEN,
    )
