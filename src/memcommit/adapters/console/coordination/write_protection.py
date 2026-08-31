"""Shared console mechanics for the distinct Lock and Unlock commands."""

from __future__ import annotations

from typing import Any

import typer

from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.local_target_lookup import (
    resolve_local_context_memory_target,
    resolve_local_direct_memory_locator,
)
from memcommit.application.capabilities.write_protection.application import (
    ContextProtectionRequest,
    MemoryProtectionRequest,
    ProfileProtectionRequest,
    WriteProtectionRequest,
    WriteProtectionResult,
)
from memcommit.application.operations.sharing_protection.lock.runtime import execute_lock
from memcommit.application.operations.sharing_protection.unlock.runtime import execute_unlock
from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.persistence.store import MemoryStore


class ProtectionCommandGroup(CanonicalCommandGroup):
    """Preserve explicit resource commands while accepting one auto target."""

    AUTO_TARGET_COMMAND = "_target"

    def collect_usage_pieces(self, ctx: Any) -> list[str]:
        pieces = super().collect_usage_pieces(ctx)
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
                command = self.get_command(ctx, self.AUTO_TARGET_COMMAND)
                if command is None:  # pragma: no cover - registration invariant
                    raise RuntimeError("Protection auto-target route is unavailable.")
                return self.AUTO_TARGET_COMMAND, command, args
        return super().resolve_command(ctx, args)


def recursive_scope(*, direct: bool, recursive: bool) -> bool:
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


def _execute_protection(
    store: MemoryStore,
    request: WriteProtectionRequest,
    *,
    protected: bool,
) -> WriteProtectionResult:
    return execute_lock(store, request) if protected else execute_unlock(store, request)


def change_context_protection(
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
        result = _execute_protection(
            store,
            ContextProtectionRequest(
                context_locator=context_name,
                current_context_name=snapshot.current_name,
                recursive=recursive,
            ),
            protected=protected,
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    assert result.context_name is not None
    display_name = display_escape_text(result.context_name)
    if recursive:
        action = "Locked" if protected else "Unlocked"
        if result.changed:
            typer.secho(
                f"{action} Context namespace '{display_name}' recursively "
                f"({result.total_count} Contexts, {result.changed_count} changed).",
                fg=typer.colors.GREEN,
            )
        else:
            state = "locked" if protected else "unlocked"
            typer.secho(
                f"Context namespace '{display_name}' is already {state} "
                f"recursively ({result.total_count} Contexts).",
                fg=typer.colors.YELLOW,
            )
        return
    if result.changed:
        action = "Locked" if protected else "Unlocked"
        typer.secho(f"{action} Context '{display_name}'.", fg=typer.colors.GREEN)
    else:
        state = "locked" if protected else "unlocked"
        typer.secho(
            f"Context '{display_name}' is already {state}.",
            fg=typer.colors.YELLOW,
        )


def change_profile_protection(*, protected: bool) -> None:
    store = MemoryStore()
    try:
        result = _execute_protection(
            store,
            ProfileProtectionRequest(),
            protected=protected,
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if result.changed:
        action = "Locked" if protected else "Unlocked"
        typer.secho(f"{action} Profile.", fg=typer.colors.GREEN)
    else:
        state = "locked" if protected else "unlocked"
        typer.secho(f"Profile is already {state}.", fg=typer.colors.YELLOW)


def change_memory_protection(
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
        result = _execute_protection(
            store,
            MemoryProtectionRequest(
                context_locator=context_name,
                memory_selector=selector,
                current_context_name=snapshot.current_name,
            ),
            protected=protected,
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

    assert result.context_name is not None
    assert result.memory_uid is not None
    display_name = display_escape_text(result.context_name)
    if result.changed:
        action = "Locked" if protected else "Unlocked"
        typer.secho(
            f"{action} Memory [{result.memory_uid[:8]}] in Context '{display_name}'.",
            fg=typer.colors.GREEN,
        )
    else:
        state = "locked" if protected else "unlocked"
        typer.secho(
            f"Memory [{result.memory_uid[:8]}] in Context '{display_name}' "
            f"is already {state}.",
            fg=typer.colors.YELLOW,
        )


def change_explicit_memory_protection(
    selector: str,
    context_name: str | None,
    *,
    protected: bool,
) -> None:
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
    change_memory_protection(
        target.memory_uid,
        target.context_name,
        protected=protected,
        store=store,
        snapshot=snapshot,
    )


def change_auto_target_protection(
    target_operand: str,
    *,
    protected: bool,
    direct: bool,
    recursive: bool,
) -> None:
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
        change_memory_protection(
            target.memory_uid,
            target.context_name,
            protected=protected,
            store=store,
            snapshot=snapshot,
        )
        return
    change_context_protection(
        target.context_name,
        protected=protected,
        recursive=recursive_scope(direct=direct, recursive=recursive),
        store=store,
        snapshot=snapshot,
    )


def change_default_protection(
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
        change_profile_protection(protected=protected)
        return
    if memory_selector is not None:
        if direct or recursive:
            raise typer.BadParameter(
                "--direct/-d and --recursive/-r apply only to a Context target."
            )
        change_explicit_memory_protection(
            memory_selector,
            context_name,
            protected=protected,
        )
        return
    change_context_protection(
        context_name,
        protected=protected,
        recursive=recursive_scope(direct=direct, recursive=recursive),
    )
