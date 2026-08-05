from dataclasses import dataclass
from typing import Annotated, Optional

import typer

from memcommit.commands.context_picker import ContextMemoryRow, choose_context
from memcommit.context import Memory, MemoryRef
from memcommit.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.commands.granted_context import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.profiles import authority_grant_snapshot_lock
from memcommit.store import ConcurrentContextUpdateError, MemoryStore
from memcommit.study_operation_policy import analysis_boundary_label


@dataclass(frozen=True)
class _GrantedPickerState:
    names: tuple[str, ...]
    annotations: dict[str, str]
    selectable_names: frozenset[str]


def _grant_annotation(permissions: tuple[str, ...]) -> str:
    """Render every permission, translating opaque storage tokens for people."""

    labels = (
        "SAVE QUERY SESSION" if permission == "SESSION_LOG" else permission
        for permission in permissions
    )
    return "[grant " + " + ".join(labels) + "]"


def _granted_picker_state(
    store: MemoryStore | None = None,
) -> _GrantedPickerState:
    """Return granted rows, exact permission labels, and navigation rights."""

    registry = load_profile_registry()
    active_store = profile_store_dir(registry.active)
    if store is None:
        store = MemoryStore(root=active_store, create=False)
    elif store.store_dir.resolve() != active_store.resolve():
        # Tests and embedders may supply an isolated store while a separate
        # host Profile is active. Never leak that host's virtual grants into
        # navigation for an unrelated storage boundary.
        return _GrantedPickerState((), {}, frozenset())
    names: dict[str, str] = {}
    selectable_names: set[str] = set()
    for grant in registry.grants:
        if grant.grantee_profile_uid != registry.active.uid:
            continue
        if not store.context_exists(grant.attachment_context_name):
            continue
        attachment = store.load_direct(grant.attachment_context_name)
        if attachment.uid != grant.attachment_context_uid:
            continue
        annotation = _grant_annotation(grant.permissions)[:-1] + " · " + (
            analysis_boundary_label(
                grant.public_name,
                granted=True,
                readable="READ" in grant.permissions,
                registry=registry,
            )
        ) + "]"
        if "READ" not in grant.permissions:
            # A query-only grant exposes its reviewed public route, never its
            # frozen authority descendants, in ordinary navigation.
            names[grant.public_name] = annotation
            selectable_names.discard(grant.public_name)
            continue
        for binding in grant.contexts:
            suffix = binding.name[len(grant.resource_name) :]
            public_name = grant.public_name + suffix
            names[public_name] = annotation
            # Navigation is authorized from structured grant data. Display
            # wording may evolve without accidentally opening a query-only row.
            selectable_names.add(public_name)
    return _GrantedPickerState(
        tuple(sorted(names)),
        names,
        frozenset(selectable_names),
    )


def _granted_picker_views(
    store: MemoryStore | None = None,
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Return granted rows and their permission labels."""

    state = _granted_picker_state(store)
    return state.names, state.annotations


def _local_picker_annotations(
    names: tuple[str, ...] | list[str],
    store: MemoryStore | None = None,
) -> dict[str, str]:
    """Expose Study-only analysis boundaries without annotating normal stores."""

    registry = load_profile_registry()
    if (
        store is not None
        and store.store_dir.resolve()
        != profile_store_dir(registry.active).resolve()
    ):
        return {}
    source = registry.active.source
    if not isinstance(source, dict) or source.get("kind") != "STUDY_RUN":
        return {}
    return {
        name: "["
        + analysis_boundary_label(
            name,
            granted=False,
            registry=registry,
        )
        + "]"
        for name in names
    }


def _picker_memory_rows(context) -> tuple[ContextMemoryRow, ...]:
    """Project direct Memories without making them selectable tree nodes."""

    rows: list[ContextMemoryRow] = []
    for item in context.iter_items():
        if isinstance(item, Memory):
            rows.append(ContextMemoryRow(f"memory {item.uid[:8]}", item.content))
        elif isinstance(item, MemoryRef):
            content = (
                item.target.content
                if item.target is not None
                else f"(dangling reference) {item.target_context_name}"
            )
            rows.append(ContextMemoryRow(f"ref {item.uid[:8]}", content))
    return tuple(rows)


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Canonical Context name, or an explicit lexical relative "
                "selector such as '.', '..', './child', or '../sibling'; "
                "omit to choose interactively"
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
                    return _picker_memory_rows(store.load(context_name))
                access = resolve_context_access(
                    store,
                    context_name,
                    current_name=expected_current,
                    required_permission="READ",
                )
                return _picker_memory_rows(
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
