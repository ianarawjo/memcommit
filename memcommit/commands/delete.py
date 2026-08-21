from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.context_targeting.tui.picker import (
    ContextMemoryRow,
    ContextMemorySelection,
    ContextPickerActionReceipt,
    choose_context,
)
from memcommit.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.console.errors import render_cli_error
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Information,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import (
    ContextDeletionCommittedError,
    MemoryStore,
    context_record_digest,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
)
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_object_label,
)


@dataclass(frozen=True)
class _ContextTarget:
    name: str
    context: Context


@dataclass(frozen=True)
class _ItemTarget:
    access: ContextAccess
    context: Context
    item: Information


def _picker_rows(context: Context) -> tuple[ContextMemoryRow, ...]:
    """Project direct items into the shared Context/Memory navigation flow."""
    rows: list[ContextMemoryRow] = []
    for item in context.iter_items():
        if isinstance(item, Memory):
            label = item.uid[:8]
            content = item.content
            style = "memory-object"
            source = SourceDisplayFacts(form=SourceForm.MEMORY)
        elif isinstance(item, MemoryRef):
            label = item.uid[:8]
            content = (
                item.target.content
                if item.target is not None
                else item.target_context_name
            )
            style = "memory-object"
            source = SourceDisplayFacts(
                form=SourceForm.MEMORY_REF,
                states=(
                    (SourceState.READ_ONLY,)
                    if item.is_resolved
                    else (SourceState.DANGLING,)
                ),
            )
        elif isinstance(item, QueryContextRef):
            label = item.uid[:8]
            content = item.name
            style = "report-neutral"
            source = SourceDisplayFacts(form=SourceForm.QUERY_VIEW)
        elif isinstance(item, Context):
            label = item.uid[:8]
            content = item.name
            style = "report-neutral"
            source = SourceDisplayFacts(reach=SourceReach.VIA_EMBED)
        else:  # pragma: no cover - Information is a closed union.
            continue
        rows.append(
            ContextMemoryRow(
                label,
                content,
                style=style,
                selector=item.uid,
                source=source,
            )
        )
    return tuple(rows)


def _choose_target(
    store: MemoryStore,
    snapshot: ContextOperandSnapshot,
    *,
    initial_target: str | ContextMemorySelection | None = None,
    item_handler: (
        Callable[[str, str], ContextPickerActionReceipt] | None
    ) = None,
) -> str | ContextMemorySelection | None:
    names = tuple(store.list_context_names())
    if not names:
        raise ValueError("No Contexts or direct items are available to delete.")
    return choose_context(
        names,
        current=snapshot.current_name,
        title="Delete or Remove · SELECT A CONTEXT OR DIRECT ITEM",
        accept_label="delete",
        exit_label="close",
        memory_loader=lambda name: _picker_rows(store.load_direct(name)),
        initially_expand_selected=True,
        initially_show_memories=True,
        selectable_memories=True,
        initial_target=initial_target,
        nested_accept_handler=item_handler,
    )


def _next_item_target(
    target: _ItemTarget,
) -> ContextMemorySelection | None:
    """Keep a repeated picker beside the item that was just removed."""
    rows_before = _picker_rows(target.context)
    removed_index = next(
        index
        for index, row in enumerate(rows_before)
        if row.selector == target.item.uid
    )
    rows_after = tuple(
        row for row in rows_before if row.selector != target.item.uid
    )
    if not rows_after:
        return None
    next_row = rows_after[min(removed_index, len(rows_after) - 1)]
    assert next_row.selector is not None
    return ContextMemorySelection(
        context_name=target.access.context_name,
        selector=next_row.selector,
    )


def _next_context_target(
    names_before: tuple[str, ...],
    removed_name: str,
) -> str | None:
    """Choose the nearest surviving Context after one interactive deletion."""
    removed_index = names_before.index(removed_name)
    names_after = tuple(name for name in names_before if name != removed_name)
    if not names_after:
        return None
    return names_after[min(removed_index, len(names_after) - 1)]


def _context_target(
    store: MemoryStore,
    snapshot: ContextOperandSnapshot,
    selector: str,
) -> _ContextTarget | None:
    """Resolve one local ordinary Context without treating grants as ownership."""
    name = snapshot.resolve(selector)
    if not store.context_exists(name):
        return None
    return _ContextTarget(name=name, context=store.load_direct(name))


def _exact_context_target(
    store: MemoryStore,
    name: str,
) -> _ContextTarget | None:
    """Load a picker-returned canonical name without reinterpreting it."""
    if not store.context_exists(name):
        return None
    return _ContextTarget(name=name, context=store.load_direct(name))


def _item_target(
    store: MemoryStore,
    snapshot: ContextOperandSnapshot,
    selector: str,
    context_name: str | None,
) -> _ItemTarget:
    access = resolve_context_access(
        store,
        context_name,
        current_name=snapshot.current_name,
        required_permission="DELETE",
    )
    context = access.store.load_direct(access.context_name)
    return _ItemTarget(
        access=access,
        context=context,
        item=ops.resolve(context, selector),
    )


def _exact_local_item_target(
    store: MemoryStore,
    context_name: str,
    selector: str,
) -> _ItemTarget:
    """Resolve one exact local picker receipt without locator re-resolution."""
    context = store.load_direct(context_name)
    access = ContextAccess(
        store=store,
        context_name=context_name,
        display_name=context_name,
        attachment_name=None,
        permission="DELETE",
    )
    return _ItemTarget(
        access=access,
        context=context,
        item=ops.resolve(context, selector),
    )


def _delete_context(
    store: MemoryStore,
    target: _ContextTarget,
    *,
    force: bool,
) -> None:
    target_digest = context_record_digest(target.context)
    display_name = display_escape_text(target.name)

    if not force:
        typer.echo(
            f"This will permanently delete context '{display_name}' and its "
            "checkpoint history, plus its matching atomize analysis and "
            "semantic review artifacts, including peer Compare analyses. "
            "Descendant contexts will be preserved. A Profile-scoped lifecycle "
            "event will retain the deleted Context identity and digests, but no "
            "Memory content or restorable snapshot."
        )
        typer.confirm("Continue?", abort=True)

    try:
        deletion_event = store.delete_context_if(
            target.name,
            expected_context_uid=target.context.uid,
            expected_context_digest=target_digest,
        )
    except ContextDeletionCommittedError as error:
        typer.secho(
            f"Deleted context '{display_name}' · ledger "
            f"[{error.event.event_uid[:8]}], but post-delete cleanup was "
            f"incomplete: {display_escape_text(str(error))}",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(1)
    except (OSError, RuntimeError, ValueError) as error:
        render_cli_error(error)
        raise typer.Exit(1)
    typer.secho(
        f"Deleted context '{display_name}' · ledger "
        f"[{deletion_event.event_uid[:8]}].",
        fg=typer.colors.GREEN,
    )


def _item_description(item: Information) -> str:
    if isinstance(item, Memory):
        return f'Removed memory [{item.uid[:8]}]: "{item.content[:80]}"'
    if isinstance(item, MemoryRef):
        label = source_object_label(SourceForm.MEMORY_REF)
        return (
            f"Removed {label} [{item.uid[:8]}] to "
            f"'{item.target_context_name}' [{item.target_memory_uid[:8]}]"
        )
    if isinstance(item, QueryContextRef):
        label = source_object_label(SourceForm.QUERY_VIEW)
        return f"Removed {label} '{item.name}' [{item.uid[:8]}]"
    if isinstance(item, Context):
        facts = SourceDisplayFacts(reach=SourceReach.VIA_EMBED)
        return (
            f"Removed {source_object_label(facts)} '{item.name}' "
            f"[{item.uid[:8]}] · {source_annotation_text(facts)}"
        )
    raise TypeError(f"Unsupported direct item type: {type(item).__name__}")


def _report_removed_item(item: Information) -> None:
    if isinstance(item, Memory):
        typer.secho(f"Removed [{item.uid[:8]}] {item.content}", fg=typer.colors.GREEN)
    elif isinstance(item, MemoryRef):
        label = source_object_label(SourceForm.MEMORY_REF)
        typer.secho(
            f"Removed {label} [{item.uid[:8]}] to "
            f"'{item.target_context_name}' [{item.target_memory_uid[:8]}].",
            fg=typer.colors.GREEN,
        )
    elif isinstance(item, QueryContextRef):
        label = source_object_label(SourceForm.QUERY_VIEW)
        typer.secho(
            f"Removed {label} '{item.name}' [{item.uid[:8]}].",
            fg=typer.colors.GREEN,
        )
    elif isinstance(item, Context):
        facts = SourceDisplayFacts(reach=SourceReach.VIA_EMBED)
        label = source_object_label(facts)
        annotation = source_annotation_text(facts)
        typer.secho(
            f"Removed {label} '{item.name}' [{item.uid[:8]}] · {annotation}",
            fg=typer.colors.GREEN,
        )


def _commit_item_deletion(target: _ItemTarget) -> Information:
    """Commit one exact deletion without choosing its presentation surface."""
    # Resolve first and then remove by the frozen full UID. This prevents an
    # ambiguous prefix from changing meaning inside this command invocation.
    item = ops.remove(target.context, target.item.uid)
    with authorized_context_mutation(target.access):
        target.access.store.save(
            target.context,
            AutoCheckpoint(
                command="remove",
                args={
                    "uid": item.uid,
                    **grant_checkpoint_args(target.access),
                },
                description=_item_description(item),
            ),
        )
    return item


def _delete_item(target: _ItemTarget) -> None:
    try:
        item = _commit_item_deletion(target)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        render_cli_error(error)
        raise typer.Exit(1)
    _report_removed_item(item)


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Existing Context locator or direct-item UID/name selector; "
                "omit to enter the shared Context/Memory picker"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context containing a direct item; disables Context selection",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "-f",
            "--force",
            help="Skip confirmation when the selector names a Context",
        ),
    ] = False,
) -> None:
    """Delete a Context or remove one direct item through one selector grammar."""
    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)

    if selector is None:
        initial_target: str | ContextMemorySelection | None = None
        attempted_item_deletions = 0
        completed_deletions = 0

        def delete_picker_item(
            selected_context_name: str,
            selected_item_uid: str,
        ) -> ContextPickerActionReceipt:
            nonlocal attempted_item_deletions, completed_deletions
            attempted_item_deletions += 1
            remove_style = "class:impact.remove"
            try:
                item_target = _exact_local_item_target(
                    store,
                    selected_context_name,
                    selected_item_uid,
                )
                removed_item = _commit_item_deletion(item_target)
            except (
                FileNotFoundError,
                KeyError,
                OSError,
                ProfileConfigError,
                ProfileError,
                RuntimeError,
                ValueError,
            ) as error:
                return ContextPickerActionReceipt(
                    label="DELETE FAILED",
                    detail=str(error),
                    label_style=remove_style,
                )
            completed_deletions += 1
            return ContextPickerActionReceipt(
                label="REMOVED",
                detail=_item_description(removed_item).removeprefix("Removed "),
                label_style=remove_style,
                detail_style=remove_style,
            )

        while True:
            try:
                selected = _choose_target(
                    store,
                    snapshot,
                    initial_target=initial_target,
                    item_handler=delete_picker_item,
                )
            except (
                FileNotFoundError,
                OSError,
                RuntimeError,
                ValueError,
            ) as error:
                if completed_deletions and not store.list_context_names():
                    return
                render_cli_error(error)
                raise typer.Exit(1)
            if selected is None:
                if not completed_deletions and not attempted_item_deletions:
                    typer.echo("Deletion cancelled.")
                return
            if isinstance(selected, ContextMemorySelection):
                try:
                    item_target = _exact_local_item_target(
                        store,
                        selected.context_name,
                        selected.selector,
                    )
                except (
                    FileNotFoundError,
                    KeyError,
                    OSError,
                    ProfileConfigError,
                    ProfileError,
                    RuntimeError,
                    ValueError,
                ) as error:
                    render_cli_error(error)
                    raise typer.Exit(1)
                initial_target = _next_item_target(item_target)
                if initial_target is None:
                    initial_target = item_target.access.context_name
                _delete_item(item_target)
                completed_deletions += 1
                continue
            names_before = tuple(store.list_context_names())
            context_target = _exact_context_target(store, selected)
            if context_target is None:
                typer.secho(
                    f"Error: Context '{display_escape_text(selected)}' no longer exists.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            initial_target = _next_context_target(names_before, selected)
            _delete_context(store, context_target, force=force)
            completed_deletions += 1

    context_target: _ContextTarget | None = None
    item_target: _ItemTarget | None = None
    context_error: Exception | None = None
    item_error: Exception | None = None

    if context_name is None:
        try:
            context_target = _context_target(store, snapshot, selector)
        except (FileNotFoundError, OSError, ValueError) as error:
            context_error = error

    try:
        item_target = _item_target(store, snapshot, selector, context_name)
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        item_error = error

    if context_target is not None and item_target is not None:
        typer.secho(
            "Error: selector "
            f"'{display_escape_text(selector)}' matches both Context "
            f"'{display_escape_text(context_target.name)}' and direct item "
            f"[{item_target.item.uid[:8]}] in "
            f"'{display_escape_text(item_target.access.display_name)}'. "
            "Use --context to select the direct item explicitly.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if context_target is not None:
        # An ambiguous direct-item prefix is still ambiguous in the combined
        # namespace; never let an exact Context silently win that collision.
        if isinstance(item_error, ValueError) and "Ambiguous" in str(item_error):
            render_cli_error(item_error)
            raise typer.Exit(1)
        _delete_context(store, context_target, force=force)
        return

    if item_target is not None:
        _delete_item(item_target)
        return

    error = item_error if context_name is not None else context_error or item_error
    if error is None:
        message = f"No Context or direct item matches '{selector}'."
    elif context_name is None and isinstance(error, (KeyError, FileNotFoundError)):
        message = f"No Context or direct item matches '{selector}'."
    else:
        message = str(error)
    render_cli_error(message)
    raise typer.Exit(1)
