"""User-facing persistent Context and Memory write protection."""

from __future__ import annotations

from typing import Annotated, Any, Optional

import typer

import memcommit.application.ops as ops
from memcommit.adapters.interfaces.cli.command_group import CanonicalCommandGroup
from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.context_targeting.loading import (
    resolve_local_context_memory_target,
    resolve_local_direct_memory_locator,
)
from memcommit.context_targeting.model import DirectMemoryTarget
from memcommit.adapters.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context import Context, Memory
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


class _ProtectionCommandGroup(CanonicalCommandGroup):
    """Preserve explicit resource commands while accepting one auto target."""

    _AUTO_TARGET_COMMAND = "_target"

    def collect_usage_pieces(self, ctx: Any) -> list[str]:
        pieces = super().collect_usage_pieces(ctx)
        # The registered subcommands remain compatibility routes.  The public
        # grammar is one optional auto-typed target, so advertise that contract
        # instead of Click's implementation-level COMMAND [ARGS] placeholder.
        if pieces:
            pieces[-1] = "[TARGET]"
        return pieces

    def resolve_command(
        self,
        ctx: Any,
        args: list[str],
    ) -> tuple[str | None, Any, list[str]]:
        if args:
            candidate = str(args[0])
            resolved = self._resolve_known_command(ctx, candidate)
            if resolved is not None:
                canonical, command = resolved
                return canonical, command, args[1:]
            if not candidate.startswith("-"):
                command = self.get_command(ctx, self._AUTO_TARGET_COMMAND)
                if command is None:  # pragma: no cover - registration invariant
                    raise RuntimeError("Protection auto-target route is unavailable.")
                return self._AUTO_TARGET_COMMAND, command, args
        return super().resolve_command(ctx, args)


lock_app = typer.Typer(
    cls=_ProtectionCommandGroup,
    no_args_is_help=False,
    invoke_without_command=True,
    help=(
        "Prevent writes to the current Context or an auto-typed Context/Memory "
        "target; use --profile for the active Profile."
    ),
)
unlock_app = typer.Typer(
    cls=_ProtectionCommandGroup,
    no_args_is_help=False,
    invoke_without_command=True,
    help=(
        "Remove protection from the current Context or an auto-typed "
        "Context/Memory target; use --profile for the active Profile."
    ),
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
    *,
    snapshot: ContextOperandSnapshot | None = None,
) -> tuple[str, Context]:
    snapshot = snapshot or ContextOperandSnapshot.capture(store)
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
    store: MemoryStore | None = None,
    snapshot: ContextOperandSnapshot | None = None,
) -> None:
    store = store or MemoryStore()
    snapshot = snapshot or ContextOperandSnapshot.capture(store)
    try:
        name, context = _context_target(
            store,
            context_name,
            snapshot=snapshot,
        )
        if recursive:
            prefix = name + "/"
            expected_contexts = tuple(
                (
                    candidate.name,
                    candidate.uid,
                    context_record_digest(candidate),
                )
                for candidate in store.load_direct_context_graph_strict()
                if candidate.name == name or candidate.name.startswith(prefix)
            )
            if not any(
                candidate_name == name for candidate_name, _, _ in expected_contexts
            ):
                raise FileNotFoundError(f"Context '{name}' not found.")
            total, changed_count = store.set_context_namespace_write_protection(
                name,
                expected_contexts,
                protected=protected,
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


def _change_explicit_memory_protection(
    selector: str,
    context_name: str | None,
    *,
    protected: bool,
) -> None:
    """Resolve an explicitly typed Memory target through the shared grammar."""

    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    try:
        target = resolve_local_direct_memory_locator(
            store,
            selector,
            current=snapshot.current_name,
            explicit_context=context_name,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    _change_memory_protection(
        target.memory_uid,
        target.context_name,
        protected=protected,
        store=store,
        snapshot=snapshot,
    )


def _change_auto_target_protection(
    target_operand: str,
    *,
    protected: bool,
    direct: bool,
    recursive: bool,
) -> None:
    """Classify one positional Context or direct-Memory target once."""

    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    try:
        target = resolve_local_context_memory_target(
            store,
            target_operand,
            current=snapshot.current_name,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if isinstance(target, DirectMemoryTarget):
        if direct or recursive:
            typer.secho(
                "Error: --direct/-d and --recursive/-r apply only to a Context target.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        _change_memory_protection(
            target.memory_uid,
            target.context_name,
            protected=protected,
            store=store,
            snapshot=snapshot,
        )
        return
    _change_context_protection(
        target.context_name,
        protected=protected,
        recursive=_recursive_scope(direct=direct, recursive=recursive),
        store=store,
        snapshot=snapshot,
    )


def _change_default_protection(
    *,
    protected: bool,
    context_name: str | None,
    memory_selector: str | None,
    profile: bool,
    direct: bool,
    recursive: bool,
) -> None:
    if profile:
        if context_name is not None or memory_selector is not None:
            raise typer.BadParameter(
                "--profile cannot be combined with --context or --memory."
            )
        if direct or recursive:
            raise typer.BadParameter(
                "--direct/-d and --recursive/-r apply only to a Context target."
            )
        _change_profile_protection(protected=protected)
        return
    if memory_selector is not None:
        if direct or recursive:
            raise typer.BadParameter(
                "--direct/-d and --recursive/-r apply only to a Context target."
            )
        _change_explicit_memory_protection(
            memory_selector,
            context_name,
            protected=protected,
        )
        return
    _change_context_protection(
        context_name,
        protected=protected,
        recursive=_recursive_scope(direct=direct, recursive=recursive),
    )


@lock_app.callback(invoke_without_command=True)
def lock_default(
    ctx: typer.Context,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Explicit Context target, or owner when --memory is supplied",
        ),
    ] = None,
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            metavar="[CONTEXT:]UID_OR_PREFIX",
            help="Explicit direct Memory target; accepts a short prefix",
        ),
    ] = None,
    profile: Annotated[
        bool,
        typer.Option(
            "--profile",
            help="Lock the active Profile",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Lock only the selected Context"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also lock existing descendants of a Context target",
        ),
    ] = False,
) -> None:
    """Lock the current Context or an explicitly typed option target."""
    if ctx.invoked_subcommand is None:
        _change_default_protection(
            protected=True,
            context_name=context_name,
            memory_selector=memory_selector,
            profile=profile,
            direct=direct,
            recursive=recursive,
        )
    elif context_name is not None or memory_selector is not None or profile:
        raise typer.BadParameter(
            "Top-level --context, --memory, and --profile cannot be combined "
            "with a compatibility resource command."
        )
    elif (direct or recursive) and ctx.invoked_subcommand not in {
        "context",
        _ProtectionCommandGroup._AUTO_TARGET_COMMAND,
    }:
        raise typer.BadParameter(
            "Context scope flags apply only to the current or an explicit "
            "Context target."
        )


@unlock_app.callback(invoke_without_command=True)
def unlock_default(
    ctx: typer.Context,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Explicit Context target, or owner when --memory is supplied",
        ),
    ] = None,
    memory_selector: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            metavar="[CONTEXT:]UID_OR_PREFIX",
            help="Explicit direct Memory target; accepts a short prefix",
        ),
    ] = None,
    profile: Annotated[
        bool,
        typer.Option(
            "--profile",
            help="Unlock the active Profile",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Unlock only the selected Context"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also unlock existing descendants of a Context target",
        ),
    ] = False,
) -> None:
    """Unlock the current Context or an explicitly typed option target."""
    if ctx.invoked_subcommand is None:
        _change_default_protection(
            protected=False,
            context_name=context_name,
            memory_selector=memory_selector,
            profile=profile,
            direct=direct,
            recursive=recursive,
        )
    elif context_name is not None or memory_selector is not None or profile:
        raise typer.BadParameter(
            "Top-level --context, --memory, and --profile cannot be combined "
            "with a compatibility resource command."
        )
    elif (direct or recursive) and ctx.invoked_subcommand not in {
        "context",
        _ProtectionCommandGroup._AUTO_TARGET_COMMAND,
    }:
        raise typer.BadParameter(
            "Context scope flags apply only to the current or an explicit "
            "Context target."
        )


def _change_memory_protection(
    selector: str,
    context_name: str | None,
    *,
    protected: bool,
    store: MemoryStore | None = None,
    snapshot: ContextOperandSnapshot | None = None,
) -> None:
    store = store or MemoryStore()
    snapshot = snapshot or ContextOperandSnapshot.capture(store)
    try:
        name, context = _context_target(
            store,
            context_name,
            snapshot=snapshot,
        )
        item = ops.resolve(context, selector)
        if not isinstance(item, Memory):
            raise TypeError(
                f"'{selector}' is not a directly owned Memory in Context '{name}'."
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
            f"Memory [{item.uid[:8]}] in Context '{display_name}' is already {state}.",
            fg=typer.colors.YELLOW,
        )


@lock_app.command(_ProtectionCommandGroup._AUTO_TARGET_COMMAND, hidden=True)
def lock_target(
    ctx: typer.Context,
    target: Annotated[
        str,
        typer.Argument(
            help="Existing Context locator, Memory UID/prefix, or CONTEXT:UID",
        ),
    ],
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Lock only a Context target"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also lock existing lexical descendants of a Context target",
        ),
    ] = False,
) -> None:
    """Lock one auto-typed Context or direct Memory target."""

    _change_auto_target_protection(
        target,
        protected=True,
        direct=direct or bool(ctx.parent and ctx.parent.params.get("direct")),
        recursive=recursive or bool(ctx.parent and ctx.parent.params.get("recursive")),
    )


@unlock_app.command(_ProtectionCommandGroup._AUTO_TARGET_COMMAND, hidden=True)
def unlock_target(
    ctx: typer.Context,
    target: Annotated[
        str,
        typer.Argument(
            help="Existing Context locator, Memory UID/prefix, or CONTEXT:UID",
        ),
    ],
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Unlock only a Context target"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Also unlock existing lexical descendants of a Context target",
        ),
    ] = False,
) -> None:
    """Unlock one auto-typed Context or direct Memory target."""

    _change_auto_target_protection(
        target,
        protected=False,
        direct=direct or bool(ctx.parent and ctx.parent.params.get("direct")),
        recursive=recursive or bool(ctx.parent and ctx.parent.params.get("recursive")),
    )


@lock_app.command("context")
def lock_context(
    ctx: typer.Context,
    context_name: Annotated[
        Optional[str],
        typer.Argument(help="Existing ordinary Context (defaults to current Context)"),
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
            direct=direct or bool(ctx.parent and ctx.parent.params.get("direct")),
            recursive=recursive
            or bool(ctx.parent and ctx.parent.params.get("recursive")),
        ),
    )


@unlock_app.command("context")
def unlock_context(
    ctx: typer.Context,
    context_name: Annotated[
        Optional[str],
        typer.Argument(help="Existing ordinary Context (defaults to current Context)"),
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
            direct=direct or bool(ctx.parent and ctx.parent.params.get("direct")),
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
        typer.Argument(help="UID or unambiguous prefix of a directly owned Memory"),
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
        typer.Argument(help="UID or unambiguous prefix of a directly owned Memory"),
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
