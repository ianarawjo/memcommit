from typing import Annotated, Optional

import typer

from memcommit.commands.context_picker import choose_context, context_memory_rows
from memcommit.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.authority.access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.context_targeting.catalog import (
    GrantedContextNavigation,
    freeze_granted_context_navigation,
    grant_navigation_annotation,
)
from memcommit.profiles import authority_grant_snapshot_lock
from memcommit.store import ConcurrentContextUpdateError, MemoryStore
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
)


_GrantedPickerState = GrantedContextNavigation


def _grant_annotation(
    permissions: tuple[str, ...],
) -> SourceDisplayValue:
    """Render Grant authority through the application-wide source grammar."""

    return grant_navigation_annotation(permissions)


def _granted_picker_state(
    store: MemoryStore | None = None,
) -> _GrantedPickerState:
    """Return granted rows, exact permission labels, and navigation rights."""

    return freeze_granted_context_navigation(store)


def _granted_picker_views(
    store: MemoryStore | None = None,
) -> tuple[tuple[str, ...], dict[str, SourceDisplayValue]]:
    """Return granted rows and their permission labels."""

    state = _granted_picker_state(store)
    return state.names, state.annotations


def _local_picker_annotations(
    names: tuple[str, ...] | list[str],
    store: MemoryStore | None = None,
) -> dict[str, str]:
    """Return no redundant annotation for locally owned history."""

    del names, store
    return {}


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Canonical Context name, or an explicit lexical relative "
                "selector such as '.', '..', './child', or '../sibling'; "
                "omit to enter the interactive Context picker"
            )
        ),
    ] = None,
) -> None:
    store = MemoryStore()
    expected_current = store.current_context_name()
    if name is None:
        names = store.list_context_names()
        if not names:
            typer.secho(
                "Error: no contexts exist. Run 'mem init <name>' first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            granted_state = _granted_picker_state(store)
            virtual_names = granted_state.names
            virtual_annotations = granted_state.annotations
            local_annotations = _local_picker_annotations(names, store)
            local_options = (
                {"local_annotations": local_annotations}
                if local_annotations
                else {}
            )

            def load_picker_memories(context_name: str):
                if context_name in names:
                    return context_memory_rows(store.load(context_name))
                access = resolve_context_access(
                    store,
                    context_name,
                    current_name=expected_current,
                    required_permission="READ",
                )
                return context_memory_rows(
                    GrantedReadStore(access).load(access.display_name)
                )

            if virtual_names:
                name = choose_context(
                    names,
                    current=expected_current,
                    accept_label="switch",
                    **local_options,
                    virtual_names=virtual_names,
                    selectable_virtual_names=granted_state.selectable_names,
                    virtual_annotations=virtual_annotations,
                    memory_loader=load_picker_memories,
                )
            else:
                name = choose_context(
                    names,
                    current=expected_current,
                    accept_label="switch",
                    **local_options,
                    memory_loader=load_picker_memories,
                )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(
                f"Error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if name is None:
            typer.echo("Switch cancelled.")
            return

    selector = name
    if is_relative_context_locator(selector):
        if expected_current is None:
            typer.secho(
                f"Error: cannot switch to '{selector}': no current context is set.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if selector == ".." and "/" not in expected_current:
            typer.secho(
                f"Error: context '{expected_current}' has no namespace parent.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            name = resolve_context_locator(
                selector,
                current=expected_current,
            )
        except ValueError as error:
            typer.secho(
                f"Error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        # Slash namespaces are lexical only. Explicit Context embeddings are
        # not unique filesystem-style parents and never affect relative paths.
        if (
            selector == ".."
            and store.context_exists(expected_current)
            and not store.context_exists(name)
        ):
            typer.secho(
                f"Error: namespace parent context '{name}' does not exist.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if (
            store.context_exists(expected_current)
            and not store.context_exists(name)
        ):
            typer.secho(
                f"Error: context '{name}' does not exist.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    try:
        access = resolve_context_access(
            store,
            name,
            current_name=expected_current,
            required_permission="READ",
        )
        target = (
            GrantedReadStore(access).load_direct(access.display_name)
            if access.is_granted
            else store.load(name)
        )
    except FileNotFoundError:
        typer.secho(
            f"Error: context '{name}' does not exist.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        typer.secho(
            f"Error: cannot switch to context '{name}': {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        # Bind both the target record and the current-state snapshot. Without
        # this CAS, a concurrent switch could be silently overwritten after a
        # relative selector or picker result was resolved.
        if access.is_granted:
            with authority_grant_snapshot_lock() as registry:
                # Resolve once more under the registry lock before publishing
                # the virtual current pointer. Later commands independently
                # reauthorize that pointer, so revocation fails closed.
                resolve_context_access(
                    store,
                    name,
                    current_name=expected_current,
                    required_permission="READ",
                    registry=registry,
                )
                store.set_current_virtual_context_if(expected_current, name)
        else:
            store.set_current_context_if(
                expected_current,
                name,
                expected_context_uid=target.uid,
                expected_context_digest=target._store_digest or "",
            )
    except (ConcurrentContextUpdateError, OSError, ValueError) as error:
        typer.secho(
            f"Error: cannot switch to context '{name}': {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if expected_current == name:
        typer.echo(f"Already on '{name}'.")
        return
    typer.secho(f"Switched to context '{name}'.", fg=typer.colors.GREEN)
