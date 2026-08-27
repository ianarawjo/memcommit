from typing import Annotated, Optional

import typer

from memcommit.context_targeting.tui.picker import choose_context, context_memory_rows
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.authority.access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.context_targeting.catalog import (
    GrantedContextNavigation,
    freeze_granted_context_navigation,
    grant_navigation_annotation,
)
from memcommit.interfaces.cli.switch import render_switch_context
from memcommit.interfaces.tui.operations.switch import (
    SwitchTuiSetup,
    run_switch_tui,
)
from memcommit.persistence.store import MemoryStore
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
)
from memcommit.application.operations.switch.application import (
    SwitchContextError,
    SwitchContextRequest,
    resolve_switch_context_name,
)
from memcommit.application.operations.switch.runtime import execute_switch_context, prepare_switch


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
    previous: Annotated[
        bool,
        typer.Option(
            "-p",
            "--previous",
            help="Switch to the previous Context in navigation history",
        ),
    ] = False,
    next_: Annotated[
        bool,
        typer.Option(
            "-n",
            "--next",
            help="Switch to the next Context after moving backward",
        ),
    ] = False,
) -> None:
    if previous and next_:
        raise typer.BadParameter("--previous and --next cannot be used together.")
    if name is not None and (previous or next_):
        raise typer.BadParameter(
            "A Context name cannot be combined with --previous or --next."
        )

    store = MemoryStore()
    expected_current = store.current_context_name()
    if previous or next_:
        request = SwitchContextRequest(
            selector=None,
            expected_current=expected_current,
            direction="PREVIOUS" if previous else "NEXT",
        )
    elif name is None:
        try:
            snapshot = prepare_switch(
                store,
                expected_current=expected_current,
            )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if not snapshot.local_context_names:
            typer.secho(
                "Error: no contexts exist. Run 'mem init <name>' first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            def load_picker_memories(context_name: str):
                if context_name in snapshot.local_context_names:
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
            request = run_switch_tui(
                SwitchTuiSetup(
                    expected_current=expected_current,
                    local_context_names=snapshot.local_context_names,
                    virtual_context_names=snapshot.granted_navigation.names,
                    selectable_virtual_names=(
                        snapshot.granted_navigation.selectable_names
                    ),
                    local_annotations=_local_picker_annotations(
                        snapshot.local_context_names,
                        store,
                    ),
                    virtual_annotations=(
                        snapshot.granted_navigation.annotations
                    ),
                    memory_loader=load_picker_memories,
                ),
                # Preserve the established command-level injection seam while
                # the concrete screen lives with its operation adapter.
                chooser=choose_context,
            )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(
                f"Error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if request is None:
            typer.echo("Switch cancelled.")
            return
    else:
        request = SwitchContextRequest(
            selector=name,
            expected_current=expected_current,
        )

    try:
        target_name = (
            resolve_switch_context_name(request)
            if request.selector is not None
            else None
        )
        result = execute_switch_context(request, store=store)
    except SwitchContextError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except FileNotFoundError:
        message = (
            f"context '{target_name}' does not exist."
            if target_name is not None
            else "saved navigation Context does not exist."
        )
        typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        target_label = (
            f"context '{target_name}'"
            if target_name is not None
            else (
                "the previous Context"
                if request.direction == "PREVIOUS"
                else "the next Context"
            )
        )
        typer.secho(
            f"Error: cannot switch to {target_label}: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    render_switch_context(result)
