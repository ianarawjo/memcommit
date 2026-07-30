from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint
from memcommit.store import MemoryStore


def cmd(
    name: Annotated[
        str,
        typer.Argument(help="Unique name for the new context"),
    ],
    parents: Annotated[
        bool,
        typer.Option(
            "--parents",
            "-p",
            help=(
                "Create missing lexical parent Contexts and reuse existing "
                "prefixes; does not embed children"
            ),
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    if not parents and store.context_exists(name):
        typer.secho(
            f"Error: context '{name}' already exists.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        if parents:
            parts = name.split("/")
            names = tuple(
                "/".join(parts[:index])
                for index in range(1, len(parts) + 1)
            )
            entries = []
            for context_name in names:
                context = ops.init(context_name)
                is_leaf = context_name == name
                description = (
                    f"Initialized context '{context_name}'"
                    if is_leaf
                    else (
                        f"Initialized namespace parent '{context_name}' "
                        f"for '{name}'"
                    )
                )
                entries.append(
                    (
                        context,
                        AutoCheckpoint(
                            command="init",
                            args={
                                "name": context_name,
                                "parents": True,
                                "requested_name": name,
                            },
                            description=description,
                        ),
                    )
                )
            created = store.create_missing_contexts(
                entries,
                make_current=name,
            )
        else:
            context = ops.init(name)
            store.create_context(
                context,
                AutoCheckpoint(
                    command="init",
                    args={"name": name},
                    description=f"Initialized context '{name}'",
                ),
            )
            created = (context,)
            store.set_current(name)
    except (OSError, RuntimeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not parents:
        typer.secho(f"Initialized context '{name}'.", fg=typer.colors.GREEN)
        return

    created_names = [context.name for context in created]
    reused_names = [
        context_name
        for context_name in names
        if context_name not in created_names
    ]
    typer.secho(
        f"Ensured context hierarchy '{name}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        "  Created: "
        + (", ".join(created_names) if created_names else "(none)")
    )
    if reused_names:
        typer.echo(f"  Reused: {', '.join(reused_names)}")
    typer.echo(f"  Current: {name}")
