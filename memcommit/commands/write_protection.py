"""User-facing persistent Context and Memory write protection."""
from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context import Context, Memory
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.store import MemoryStore, context_record_digest


lock_app = typer.Typer(
    no_args_is_help=False,
    invoke_without_command=True,
    help="Prevent writes to the current Context, a target, or the Profile.",
)
unlock_app = typer.Typer(
    no_args_is_help=False,
    invoke_without_command=True,
    help="Remove current-Context, target, or Profile write protection.",
)


def _recursive_scope(*, direct: bool, recursive: bool) -> bool:
    try:
        return (
            resolve_scope_preset(
                direct=direct,
                recursive=recursive,
                default=ContextScopePreset.DIRECT,
            )
            is ContextScopePreset.RECURSIVE
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def _context_target(
    store: MemoryStore,
    locator: str | None,
) -> tuple[str, Context]:
    snapshot = ContextOperandSnapshot.capture(store)
    name = snapshot.resolve_or_current(locator)
    if not name:
        raise RuntimeError(
            "No current context. Pass CONTEXT or run 'mem init <name>' first."
        )
    return name, store.load_direct(name)


def _change_context_protection(
    context_name: str | None,
    *,
    protected: bool,
    recursive: bool = False,
) -> None:
    store = MemoryStore()
    try:
        name, context = _context_target(store, context_name)
        if recursive:
            prefix = name + "/"
            expected_contexts = tuple(
                (
                    candidate.name,
                    candidate.uid,
                    context_record_digest(candidate),
                )
                for candidate in store.load_direct_context_graph_strict()
                if candidate.name == name
                or candidate.name.startswith(prefix)
            )
            if not any(
                candidate_name == name
                for candidate_name, _, _ in expected_contexts
            ):
                raise FileNotFoundError(f"Context '{name}' not found.")
            total, changed_count = (
                store.set_context_namespace_write_protection(
                    name,
                    expected_contexts,
                    protected=protected,
                )
            )
            changed = changed_count > 0
        else:
            changed = store.set_context_write_protection(
                name,
                protected=protected,
                expected_context_uid=context.uid,
                expected_context_digest=context_record_digest(context),
            )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    display_name = display_escape_text(name)
    if recursive:
        action = "Locked" if protected else "Unlocked"
        if changed:
            typer.secho(
                f"{action} Context namespace '{display_name}' recursively "
                f"({total} Contexts, {changed_count} changed).",
                fg=typer.colors.GREEN,
            )
        else:
            state = "locked" if protected else "unlocked"
            typer.secho(
                f"Context namespace '{display_name}' is already {state} "
                f"recursively ({total} Contexts).",
                fg=typer.colors.YELLOW,
            )
        return
    if changed:
        action = "Locked" if protected else "Unlocked"
        typer.secho(f"{action} Context '{display_name}'.", fg=typer.colors.GREEN)
    else:
        state = "locked" if protected else "unlocked"
        typer.secho(
            f"Context '{display_name}' is already {state}.",
            fg=typer.colors.YELLOW,
        )


def _change_profile_protection(*, protected: bool) -> None:
    store = MemoryStore()
    try:
        changed = store.set_profile_write_protection(protected=protected)
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if changed:
        action = "Locked" if protected else "Unlocked"
        typer.secho(f"{action} Profile.", fg=typer.colors.GREEN)
    else:
        state = "locked" if protected else "unlocked"
        typer.secho(
            f"Profile is already {state}.",
            fg=typer.colors.YELLOW,
        )


@lock_app.callback(invoke_without_command=True)
def lock_default(
    ctx: typer.Context,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Lock only the current Context"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="With no subcommand, also lock existing descendants",
        ),
    ] = False,
) -> None:
    """Lock the current Context when no target subcommand is supplied."""
    if ctx.invoked_subcommand is None:
        _change_context_protection(
            None,
            protected=True,
            recursive=_recursive_scope(direct=direct, recursive=recursive),
        )
    elif (direct or recursive) and ctx.invoked_subcommand != "context":
        raise typer.BadParameter(
            "Context scope flags apply only to the current Context or the "
            "context subcommand."
        )


@unlock_app.callback(invoke_without_command=True)
def unlock_default(
    ctx: typer.Context,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Unlock only the current Context"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="With no subcommand, also unlock existing descendants",
        ),
    ] = False,
) -> None:
    """Unlock the current Context when no target subcommand is supplied."""
    if ctx.invoked_subcommand is None:
        _change_context_protection(
            None,
            protected=False,
            recursive=_recursive_scope(direct=direct, recursive=recursive),
        )
    elif (direct or recursive) and ctx.invoked_subcommand != "context":
        raise typer.BadParameter(
            "Context scope flags apply only to the current Context or the "
            "context subcommand."
        )


def _change_memory_protection(
    selector: str,
    context_name: str | None,
    *,
    protected: bool,
) -> None:
    store = MemoryStore()
    try:
        name, context = _context_target(store, context_name)
        item = ops.resolve(context, selector)
        if not isinstance(item, Memory):
            raise TypeError(
                f"'{selector}' is not a directly owned Memory in Context "
                f"'{name}'."
            )
        changed = store.set_memory_write_protection(
            name,
            item.uid,
            protected=protected,
            expected_context_uid=context.uid,
            expected_context_digest=context_record_digest(context),
        )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    display_name = display_escape_text(name)
    if changed:
        action = "Locked" if protected else "Unlocked"
        typer.secho(
            f"{action} Memory [{item.uid[:8]}] in Context '{display_name}'.",
            fg=typer.colors.GREEN,
        )
    else:
        state = "locked" if protected else "unlocked"
        typer.secho(
            f"Memory [{item.uid[:8]}] in Context '{display_name}' is already "
            f"{state}.",
            fg=typer.colors.YELLOW,
        )


@lock_app.command("context")
def lock_context(
    ctx: typer.Context,
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            help="Existing ordinary Context (defaults to current Context)"
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Lock only the selected Context"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also lock existing lexical descendants atomically",
        ),
    ] = False,
) -> None:
    """Prevent content, structure, rename, and deletion changes."""
    _change_context_protection(
        context_name,
        protected=True,
        recursive=_recursive_scope(
            direct=direct
            or bool(ctx.parent and ctx.parent.params.get("direct")),
            recursive=recursive
            or bool(ctx.parent and ctx.parent.params.get("recursive")),
        ),
    )


@unlock_app.command("context")
def unlock_context(
    ctx: typer.Context,
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            help="Existing ordinary Context (defaults to current Context)"
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Unlock only the selected Context"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also unlock existing lexical descendants atomically",
        ),
    ] = False,
) -> None:
    """Allow changes to a previously protected Context."""
    _change_context_protection(
        context_name,
        protected=False,
        recursive=_recursive_scope(
            direct=direct
            or bool(ctx.parent and ctx.parent.params.get("direct")),
            recursive=recursive
            or bool(ctx.parent and ctx.parent.params.get("recursive")),
        ),
    )


@lock_app.command("profile")
def lock_profile() -> None:
    """Prevent durable writes anywhere inside the active Profile."""
    _change_profile_protection(protected=True)


@unlock_app.command("profile")
def unlock_profile() -> None:
    """Allow Profile writes, preserving narrower Context/Memory locks."""
    _change_profile_protection(protected=False)


@lock_app.command("memory")
def lock_memory(
    selector: Annotated[
        str,
        typer.Argument(
            help="UID or unambiguous prefix of a directly owned Memory"
        ),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Existing ordinary Context (defaults to current Context)",
        ),
    ] = None,
) -> None:
    """Prevent editing or removing one direct Memory occurrence."""
    _change_memory_protection(selector, context_name, protected=True)


@unlock_app.command("memory")
def unlock_memory(
    selector: Annotated[
        str,
        typer.Argument(
            help="UID or unambiguous prefix of a directly owned Memory"
        ),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Existing ordinary Context (defaults to current Context)",
        ),
    ] = None,
) -> None:
    """Allow editing or removing one protected direct Memory occurrence."""
    _change_memory_protection(selector, context_name, protected=False)
