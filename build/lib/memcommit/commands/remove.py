from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.granted_context import (
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def cmd(
    uid: Annotated[
        str,
        typer.Argument(help="UID (or unambiguous prefix) of the item to remove"),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Local Context or granted view containing the item",
        ),
    ] = None,
) -> None:
    active_store = MemoryStore()
    try:
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=active_store.current_context_name(),
            required_permission="DELETE",
        )
        store = access.store
        ctx = store.load_direct(access.context_name)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        item = ops.remove(ctx, uid)
    except (KeyError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if isinstance(item, Memory):
        description = f'Removed memory [{item.uid[:8]}]: "{item.content[:80]}"'
    elif isinstance(item, MemoryRef):
        description = (
            f"Removed memory reference [{item.uid[:8]}] to "
            f"'{item.target_context_name}' [{item.target_memory_uid[:8]}]"
        )
    elif isinstance(item, QueryContextRef):
        description = (
            f"Removed query-only Context '{item.name}' [{item.uid[:8]}]"
        )
    elif isinstance(item, Context):
        description = f"Removed embedded context '{item.name}' [{item.uid[:8]}]"

    try:
        with authorized_context_mutation(access):
            store.save(ctx, AutoCheckpoint(
                command="remove",
                args={"uid": item.uid, **grant_checkpoint_args(access)},
                description=description,
            ))
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if isinstance(item, Memory):
        typer.secho(f"Removed [{item.uid[:8]}] {item.content}", fg=typer.colors.GREEN)
    elif isinstance(item, MemoryRef):
        typer.secho(
            f"Removed reference [{item.uid[:8]}] to "
            f"'{item.target_context_name}' [{item.target_memory_uid[:8]}].",
            fg=typer.colors.GREEN,
        )
    elif isinstance(item, QueryContextRef):
        typer.secho(
            f"Removed query-only Context '{item.name}' [{item.uid[:8]}].",
            fg=typer.colors.GREEN,
        )
    elif isinstance(item, Context):
        typer.secho(f"Removed embedded context '{item.name}' [{item.uid[:8]}]", fg=typer.colors.GREEN)
