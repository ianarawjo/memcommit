from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint
from memcommit.context_targeting.tui.name_editor import (
    ContextNameView,
    choose_context_name,
    suggest_fresh_context_name,
)
from memcommit.store import MemoryStore, validate_context_name


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Unique name for the new Context; omit in a terminal to edit "
                "a suggested fresh name"
            )
        ),
    ] = None,
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
    expected_current = store.current_context_name()
    context_names = tuple(store.list_context_names())
    if name is None:
        suggestion = suggest_fresh_context_name("new-context", context_names)
        validator = validate_context_name if parents else store.assert_context_creatable
        try:
            name = choose_context_name(
                ContextNameView(
                    value=suggestion,
                    label="NEW CONTEXT NAME",
                    state="NOT CREATED",
                    detail="Enter creates this exact Context and switches to it.",
                    validate=validator,
                    context_names=context_names,
                    current_context=expected_current,
                )
            )
        except (OSError, TypeError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if name is None:
            typer.echo("Initialization cancelled — no Context was created.")
            return
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
            names = tuple("/".join(parts[:index]) for index in range(1, len(parts) + 1))
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
                expected_current=expected_current,
            )
        else:
            context = ops.init(name)
            created = store.create_missing_contexts(
                (
                    (
                        context,
                        AutoCheckpoint(
                            command="init",
                            args={"name": name},
                            description=f"Initialized context '{name}'",
                        ),
                    ),
                ),
                make_current=name,
                require_all_new=True,
                expected_current=expected_current,
            )
    except (OSError, RuntimeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not parents:
        typer.secho(f"Initialized context '{name}'.", fg=typer.colors.GREEN)
        return

    created_names = [context.name for context in created]
    reused_names = [
        context_name for context_name in names if context_name not in created_names
    ]
    typer.secho(
        f"Ensured context hierarchy '{name}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        "  Created: " + (", ".join(created_names) if created_names else "(none)")
    )
    if reused_names:
        typer.echo(f"  Reused: {', '.join(reused_names)}")
    typer.echo(f"  Current: {name}")
