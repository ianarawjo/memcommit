from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Optional

import typer

from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.core.context_targeting.tui.picker import (
    ContextMemorySelection,
    ContextPickerActionReceipt,
    choose_context,
)
from memcommit.core.context_targeting.loading import DirectItemAmbiguityError
from memcommit.core.context_targeting.model import DirectItemTarget
from memcommit.application.operations.delete.application import (
    DeleteError,
    DeleteStalePlanError,
    DirectItemDeleteRequest,
    FrozenContextDeletePlan,
    FrozenDirectItemDeleteTarget,
    apply_context_delete,
    run_direct_item_delete,
)
from memcommit.application.operations.delete.runtime import MemoryStoreDeletePort
from memcommit.adapters.interfaces.cli.delete import (
    context_delete_warning,
    removed_item_description,
    render_context_delete_result,
    render_removed_item,
)
from memcommit.adapters.interfaces.console.errors import render_cli_error
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.adapters.interfaces.tui.operations.delete import (
    choose_delete_target,
    delete_picker_rows,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True, slots=True)
class _PreparedDeleteTarget:
    """One argv selector bound to exactly one reviewed deletion target."""

    selector: str
    target: FrozenContextDeletePlan | FrozenDirectItemDeleteTarget


def _choose_target(
    store: MemoryStore,
    snapshot: ContextOperandSnapshot,
    *,
    initial_target: str | ContextMemorySelection | None = None,
    item_handler: Callable[[str, str], ContextPickerActionReceipt] | None = None,
) -> str | ContextMemorySelection | None:
    """Compatibility composition over the shared Delete picker adapter."""

    return choose_delete_target(
        store,
        current_name=snapshot.current_name,
        initial_target=initial_target,
        item_handler=item_handler,
        # Keep the historical command symbol patchable for focused adapter
        # tests while all picker mechanics live in the TUI interface module.
        chooser=choose_context,
    )


def _next_item_target(
    store: MemoryStore,
    target: FrozenDirectItemDeleteTarget,
) -> ContextMemorySelection | None:
    """Keep a repeated picker beside the item that is about to be removed."""

    context = store.load_direct(target.context_name)
    rows_before = delete_picker_rows(context)
    removed_index = next(
        index for index, row in enumerate(rows_before) if row.selector == target.item.uid
    )
    rows_after = tuple(
        row for row in rows_before if row.selector != target.item.uid
    )
    if not rows_after:
        return None
    next_row = rows_after[min(removed_index, len(rows_after) - 1)]
    assert next_row.selector is not None
    return ContextMemorySelection(
        context_name=target.context_name,
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


def _context_plan(
    store: MemoryStore,
    snapshot: ContextOperandSnapshot,
    port: MemoryStoreDeletePort,
    selector: str,
) -> FrozenContextDeletePlan | None:
    """Resolve one local Context against the command-start current snapshot."""

    name = snapshot.resolve(selector)
    if not store.context_exists(name):
        return None
    return port.freeze_exact_context(name)


def _exact_context_plan(
    store: MemoryStore,
    port: MemoryStoreDeletePort,
    name: str,
) -> FrozenContextDeletePlan | None:
    """Load a picker-returned canonical name without reinterpreting it."""

    if not store.context_exists(name):
        return None
    return port.freeze_exact_context(name)


def _item_target(
    port: MemoryStoreDeletePort,
    selector: str,
    context_name: str | None,
) -> FrozenDirectItemDeleteTarget:
    return port.freeze_item(
        DirectItemDeleteRequest(
            selector=selector,
            context_locator=context_name,
        )
    )


def _picked_item_target(
    port: MemoryStoreDeletePort,
    context_name: str,
    item_uid: str,
) -> FrozenDirectItemDeleteTarget:
    """Normalize a picker receipt into the shared exact item coordinate."""

    return port.freeze_local_item_target(
        DirectItemTarget(context_name=context_name, item_uid=item_uid)
    )


def _delete_context(
    port: MemoryStoreDeletePort,
    plan: FrozenContextDeletePlan,
    *,
    force: bool,
) -> None:
    if not force:
        typer.echo(context_delete_warning(plan))
        typer.confirm("Continue?", abort=True)
    try:
        result = apply_context_delete(plan, port=port)
    except (OSError, RuntimeError, ValueError) as error:
        render_cli_error(error)
        raise typer.Exit(1)
    render_context_delete_result(result)
    if result.status == "APPLIED_WITH_CLEANUP_WARNING":
        # The primary deletion is already committed. Preserve the historical
        # nonzero human receipt without representing it as safe to retry.
        raise typer.Exit(1)


def _delete_item(
    port: MemoryStoreDeletePort,
    target: FrozenDirectItemDeleteTarget,
) -> None:
    try:
        result = run_direct_item_delete(
            DirectItemDeleteRequest(
                selector=target.item.uid,
                context_locator=target.context_name,
            ),
            port=port,
            frozen_target=target,
        )
    except (
        DeleteError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        render_cli_error(error)
        raise typer.Exit(1)
    render_removed_item(result)


def _prepare_explicit_target(
    store: MemoryStore,
    snapshot: ContextOperandSnapshot,
    port: MemoryStoreDeletePort,
    selector: str,
    context_name: str | None,
) -> _PreparedDeleteTarget:
    """Resolve one selector through the established combined target grammar."""

    context_plan: FrozenContextDeletePlan | None = None
    item_target: FrozenDirectItemDeleteTarget | None = None
    context_error: Exception | None = None
    item_error: Exception | None = None

    if context_name is None:
        try:
            context_plan = _context_plan(store, snapshot, port, selector)
        except (FileNotFoundError, OSError, ValueError) as error:
            context_error = error

    try:
        item_target = _item_target(port, selector, context_name)
    except (
        DeleteError,
        FileNotFoundError,
        KeyError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        item_error = error

    if context_plan is not None and item_target is not None:
        raise ValueError(
            "selector "
            f"'{selector}' matches both Context "
            f"'{context_plan.context_name}' and direct item "
            f"[{item_target.item.uid[:8]}] in "
            f"'{item_target.context_name}'. "
            "Use --context to select the direct item explicitly."
        )

    if context_plan is not None:
        # An ambiguous item prefix remains ambiguous in the combined namespace;
        # never let an exact Context silently win that collision.
        if isinstance(item_error, DirectItemAmbiguityError):
            raise item_error
        return _PreparedDeleteTarget(selector, context_plan)

    if item_target is not None:
        return _PreparedDeleteTarget(selector, item_target)

    failure = item_error if item_error is not None else context_error
    if failure is None:
        raise ValueError(f"No Context or direct item matches '{selector}'.")
    if context_name is None and isinstance(failure, KeyError):
        raise ValueError(f"No Context or direct item matches '{selector}'.")
    raise failure


def _target_identity(
    prepared: _PreparedDeleteTarget,
) -> tuple[str, ...]:
    target = prepared.target
    if isinstance(target, FrozenContextDeletePlan):
        return ("context", target.context_uid)
    return ("item", target.context_uid, target.item.uid)


def _validate_explicit_batch(
    prepared_targets: tuple[_PreparedDeleteTarget, ...],
) -> None:
    """Reject duplicate and overlapping effects before publishing any change."""

    seen: dict[tuple[str, ...], _PreparedDeleteTarget] = {}
    for prepared in prepared_targets:
        identity = _target_identity(prepared)
        previous = seen.get(identity)
        if previous is not None:
            raise ValueError(
                f"selectors '{previous.selector}' and '{prepared.selector}' "
                "resolve to the same deletion target."
            )
        seen[identity] = prepared

    context_plans = {
        target.context_uid: target
        for prepared in prepared_targets
        if isinstance((target := prepared.target), FrozenContextDeletePlan)
    }
    for prepared in prepared_targets:
        target = prepared.target
        if not isinstance(target, FrozenDirectItemDeleteTarget):
            continue
        owner_plan = context_plans.get(target.context_uid)
        if owner_plan is None:
            continue
        raise ValueError(
            f"batch selects Context '{owner_plan.context_name}' and direct item "
            f"[{target.item.uid[:8]}] owned by that Context. Remove either the "
            "Context selector or its direct-item selector."
        )


def _refresh_item_target(
    port: MemoryStoreDeletePort,
    prepared: FrozenDirectItemDeleteTarget,
) -> FrozenDirectItemDeleteTarget:
    """Reload one reviewed UID so same-owner batch checkpoints compose safely."""

    try:
        refreshed = port.freeze_item(
            DirectItemDeleteRequest(
                selector=prepared.item.uid,
                context_locator=prepared.context_name,
            )
        )
    except (
        DeleteError,
        FileNotFoundError,
        KeyError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        raise DeleteStalePlanError(
            f"Direct item [{prepared.item.uid[:8]}] in "
            f"'{prepared.context_name}' changed after deletion was reviewed."
        ) from error
    if (
        refreshed.context_name != prepared.context_name
        or refreshed.context_uid != prepared.context_uid
        or refreshed.item != prepared.item
    ):
        raise DeleteStalePlanError(
            f"Direct item [{prepared.item.uid[:8]}] in "
            f"'{prepared.context_name}' changed after deletion was reviewed."
        )
    return refreshed


def _revalidate_explicit_batch(
    port: MemoryStoreDeletePort,
    prepared_targets: tuple[_PreparedDeleteTarget, ...],
) -> None:
    """Recheck every reviewed identity after approval and before first Apply."""

    for prepared in prepared_targets:
        target = prepared.target
        if isinstance(target, FrozenDirectItemDeleteTarget):
            _refresh_item_target(port, target)
            continue
        try:
            refreshed = port.freeze_exact_context(target.context_name)
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            raise DeleteStalePlanError(
                f"Context '{target.context_name}' changed after deletion was reviewed."
            ) from error
        if (
            refreshed.context_uid != target.context_uid
            or refreshed.context_digest != target.context_digest
            or refreshed.plan_digest != target.plan_digest
        ):
            raise DeleteStalePlanError(
                f"Context '{target.context_name}' changed after deletion was reviewed."
            )


def cmd(
    selectors: Annotated[
        Optional[list[str]],
        typer.Argument(
            metavar="[SELECTOR]...",
            help=(
                "Existing Context locators or direct-item UID/name selectors; "
                "omit to enter the shared Context/Memory picker"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help=(
                "Context containing every selected direct item; disables "
                "Context selection"
            ),
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "-f",
            "--force",
            help="Skip confirmation when any selector names a Context",
        ),
    ] = False,
) -> None:
    """Delete Contexts or direct items through one mixed selector grammar."""

    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    # Every relative locator in this command uses the same captured current
    # Context; approval cannot be retargeted by a later global switch.
    port = MemoryStoreDeletePort(store, current_name=snapshot.current_name)

    if not selectors:
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
                item_target = _picked_item_target(
                    port,
                    selected_context_name,
                    selected_item_uid,
                )
                removed = run_direct_item_delete(
                    DirectItemDeleteRequest(
                        selector=selected_item_uid,
                        context_locator=selected_context_name,
                    ),
                    port=port,
                    frozen_target=item_target,
                )
            except (
                DeleteError,
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
                detail=removed_item_description(removed.item),
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
            except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
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
                    picked_item_target = _picked_item_target(
                        port,
                        selected.context_name,
                        selected.selector,
                    )
                    initial_target = _next_item_target(store, picked_item_target)
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
                if initial_target is None:
                    initial_target = picked_item_target.context_name
                _delete_item(port, picked_item_target)
                completed_deletions += 1
                continue
            names_before = tuple(store.list_context_names())
            picked_context_plan = _exact_context_plan(store, port, selected)
            if picked_context_plan is None:
                typer.secho(
                    f"Error: Context '{display_escape_text(selected)}' no longer exists.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            initial_target = _next_context_target(names_before, selected)
            _delete_context(port, picked_context_plan, force=force)
            completed_deletions += 1

    try:
        prepared_targets = tuple(
            _prepare_explicit_target(
                store,
                snapshot,
                port,
                selector,
                context_name,
            )
            for selector in selectors
        )
        _validate_explicit_batch(prepared_targets)
    except (
        DeleteError,
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

    context_plans = tuple(
        target
        for prepared in prepared_targets
        if isinstance((target := prepared.target), FrozenContextDeletePlan)
    )
    if context_plans and not force:
        for plan in context_plans:
            typer.echo(context_delete_warning(plan))
        typer.confirm("Continue?", abort=True)

    try:
        _revalidate_explicit_batch(port, prepared_targets)
    except (
        DeleteError,
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

    for prepared in prepared_targets:
        target = prepared.target
        if isinstance(target, FrozenContextDeletePlan):
            # The complete irreversible set was already reviewed together.
            _delete_context(port, target, force=True)
            continue
        try:
            refreshed_item = _refresh_item_target(port, target)
        except (
            DeleteError,
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
        _delete_item(port, refreshed_item)
