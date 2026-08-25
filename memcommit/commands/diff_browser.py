"""Shared location-first browser for Diff and Revert checkpoints."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace as dataclass_replace

from memcommit.commands.checkpoint_diff import (
    checkpoint_revision_detail_renderer,
)
from memcommit.context_targeting.tui.picker import (
    ContextMemoryBadge,
    ContextMemoryDetail,
    ContextMemoryRow,
    ContextSubtreeSelection,
)
from memcommit.interfaces.tui.components.checkpoint_location import (
    CheckpointLocationSelection,
    choose_history_location,
)
from memcommit.commands.history_picker import (
    HISTORY_BACK,
    HistoryBackNavigation,
    HistoryPickerMode,
    HistorySelectionReceipt,
    choose_history,
    revert_exact_command_review,
)
from memcommit.commands.history_present import checkpoint_picker_entries
from memcommit.commands.update_checkpoint_history import (
    choose_update_checkpoint_at_location,
    choose_update_checkpoint_subtree,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.checkpoint_catalog import (
    ResolvedCheckpointUnit,
    freeze_checkpoint_catalog,
)
from memcommit.history_display import (
    HistoryDisplayRow,
    checkpoint_command_identity,
    checkpoint_inherited_from,
    project_history_display_rows,
)
from memcommit.interfaces.tui.core.theme import semantic_action_style
from memcommit.store import (
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
)
from memcommit.update import UpdateSession


@dataclass(frozen=True)
class ReviewedCheckpointSelection:
    """One exact mutation target frozen before its History approval screen."""

    context_name: str
    context_uid: str
    context_digest: str
    history_digest: str
    checkpoint_uid: str
    keep_history: bool
    checkpoint_unit: ResolvedCheckpointUnit


def _update_locations(session: UpdateSession | None) -> tuple[str, ...]:
    if session is None:
        return ()
    return tuple(
        dict.fromkeys(operation.owner_context_name for operation in session.operations)
    )


def _checkpoint_operation_identity(checkpoint: Mapping[str, object]) -> str | None:
    """Return the command-unit identity represented by one checkpoint file."""

    return checkpoint_command_identity(checkpoint)


def _local_operation_ids(
    store: MemoryStore,
    names: Sequence[str],
    *,
    manual: bool = False,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    direct: dict[str, set[str]] = {}
    inherited: dict[str, set[str]] = {}
    for name in names:
        context = store.load_direct(name)
        checkpoints = [
            checkpoint
            for checkpoint in store.list_checkpoints(name)
            if not manual or not checkpoint.get("auto", False)
        ]
        direct[name] = set()
        inherited[name] = set()
        for checkpoint in checkpoints:
            identity = _checkpoint_operation_identity(checkpoint)
            if identity is None:
                continue
            destination = (
                inherited
                if checkpoint_inherited_from(
                    checkpoint,
                    context_name=name,
                    context_uid=context.uid,
                )
                is not None
                else direct
            )
            destination[name].add(identity)
    return direct, inherited


def _update_operation_ids(session: UpdateSession | None) -> dict[str, set[str]]:
    """Project participant-visible Update lifecycle operations by owner."""

    if session is None or session.application is None:
        return {}
    update_uid = f"update:{session.uid}:{session.application.operation_digest}"
    identities = {update_uid}
    if session.status == "undone":
        # Schema v6 retains current restoration state but not the authority's
        # private receipt UID. UNDONE still proves one visible Undo after this
        # retained Update, which is sufficient for the current lifecycle count.
        identities.add(f"restore:undo:{update_uid}")
    return {name: set(identities) for name in _update_locations(session)}


def _operation_annotations(
    catalog: Sequence[str],
    operations_by_name: Mapping[str, set[str]],
    inherited_by_name: Mapping[str, set[str]] | None = None,
) -> dict[str, str]:
    """Count distinct direct and descendant command units for every row."""

    annotations: dict[str, str] = {}
    for name in catalog:
        direct = operations_by_name.get(name, set())
        inherited = (inherited_by_name or {}).get(name, set())
        prefix = name + "/"
        descendants: set[str] = set()
        for owner, identities in operations_by_name.items():
            if owner.startswith(prefix):
                descendants.update(identities)
        annotations[name] = (
            f"{len(direct)} direct · {len(inherited)} inherited · "
            f"{len(descendants)} descendant commands"
        )
    return annotations


def _checkpoint_operation_rows(
    checkpoints: Sequence[Mapping[str, object]],
    *,
    context_name: str,
    context_uid: str,
) -> tuple[ContextMemoryRow, ...]:
    """Project typed direct and inherited command rows plus creation baseline."""

    creation_atomize_uids = {
        source_uid
        for checkpoint in checkpoints
        if checkpoint.get("command") == "init"
        and isinstance(checkpoint.get("args"), Mapping)
        and isinstance(
            source_uid := checkpoint["args"].get("source_analysis_uid"),
            str,
        )
        and source_uid
    }
    atomize_creation_checkpoints = {
        checkpoint_uid
        for checkpoint in checkpoints
        if checkpoint.get("command") == "init"
        and isinstance(checkpoint.get("args"), Mapping)
        and checkpoint["args"].get("source_analysis_uid") in creation_atomize_uids
        and isinstance(checkpoint_uid := checkpoint.get("uid"), str)
        and checkpoint_uid
    }
    filtered = tuple(
        checkpoint
        for checkpoint in checkpoints
        if not (
            checkpoint.get("command") == "atomize"
            and isinstance(checkpoint.get("args"), Mapping)
            and checkpoint["args"].get("analysis_uid") in creation_atomize_uids
        )
    )
    return _context_rows_from_history(
        project_history_display_rows(
            filtered,
            context_name=context_name,
            context_uid=context_uid,
        ),
        context_name=context_name,
        atomize_creation_checkpoints=atomize_creation_checkpoints,
    )


def _context_rows_from_history(
    rows: Sequence[HistoryDisplayRow],
    *,
    context_name: str,
    atomize_creation_checkpoints: set[str] | None = None,
) -> tuple[ContextMemoryRow, ...]:
    projected: list[ContextMemoryRow] = []
    last_section: str | None = None
    for row in rows:
        section = (
            f"INHERITED HISTORY · source {row.inherited_from}"
            if row.inherited_from is not None
            else f"DIRECT COMMANDS · {context_name}"
        )
        section_label = section if section != last_section else None
        last_section = section
        badges = [ContextMemoryBadge(badge.text, badge.style) for badge in row.badges]
        if (
            row.is_creation
            and atomize_creation_checkpoints
            and row.checkpoint_uid in atomize_creation_checkpoints
        ):
            badges.insert(1, ContextMemoryBadge("ATOMIZE", "history-source"))
        projected.append(
            ContextMemoryRow(
                row.command,
                f"{row.timestamp} · {row.summary}",
                style="report-neutral",
                selector=row.checkpoint_uid,
                label_style=(
                    semantic_action_style(row.command).removeprefix("class:") or None
                ),
                badges=tuple(badges),
                section_label=section_label,
                detail_title=f"{row.command.upper()} · {row.summary}",
                details=tuple(
                    ContextMemoryDetail(detail.label, detail.value, detail.style)
                    for detail in row.details
                ),
            )
        )
    return tuple(projected)


def _checkpoint_version_rows(
    checkpoints: Sequence[Mapping[str, object]],
    *,
    context_name: str,
    context_uid: str,
) -> tuple[ContextMemoryRow, ...]:
    """Project every exact restorable version without operation deduplication.

    The Context stage is allowed to choose a checkpoint, but it does not decide
    whether that checkpoint is a useful or legal Revert result. In particular,
    correlated Init/Atomize records and repeated command identities remain
    independently focusable because they represent different persisted states.
    """

    return _context_rows_from_history(
        project_history_display_rows(
            checkpoints,
            context_name=context_name,
            context_uid=context_uid,
            deduplicate_commands=False,
        ),
        context_name=context_name,
    )


def _update_operation_rows(
    session: UpdateSession | None,
    name: str,
) -> tuple[ContextMemoryRow, ...]:
    if (
        session is None
        or session.application is None
        or name not in _update_locations(session)
    ):
        return ()
    operation_count = sum(
        operation.owner_context_name == name for operation in session.operations
    )
    checkpoint_uid = next(
        (
            receipt.checkpoint_uid
            for receipt in session.application.checkpoints
            if receipt.context_name == name
        ),
        "(pending)",
    )
    checkpoint_badge = (
        checkpoint_uid[:8] if checkpoint_uid != "(pending)" else checkpoint_uid
    )
    rows = [
        ContextMemoryRow(
            "update",
            f"{operation_count} Memory changes",
            style="report-neutral",
            label_style=(
                semantic_action_style("update").removeprefix("class:") or None
            ),
            badges=(ContextMemoryBadge(f"CHECKPOINT {checkpoint_badge}"),),
            section_label=f"DIRECT COMMANDS · {name}",
            detail_title=f"UPDATE · {operation_count} Memory changes",
            details=(
                ContextMemoryDetail("Checkpoint", checkpoint_uid),
                ContextMemoryDetail("History role", f"direct · {name}"),
            ),
        )
    ]
    if session.status == "undone":
        rows.insert(
            0,
            ContextMemoryRow(
                "undo",
                "restored the retained Update operation",
                style="report-neutral",
                label_style=(
                    semantic_action_style("undo").removeprefix("class:") or None
                ),
                section_label=f"DIRECT COMMANDS · {name}",
            ),
        )
        rows[1] = dataclass_replace(rows[1], section_label=None)
    return tuple(rows)


def _browse_local_checkpoints(
    store: MemoryStore,
    context_name: str,
    *,
    back_navigation: bool = False,
    manual: bool = False,
    show_diffs: bool = True,
    mode: HistoryPickerMode = "log",
    keep_history: bool = False,
    staged_checkpoint_uid: str | None = None,
    title: str | None = None,
) -> ReviewedCheckpointSelection | HistoryBackNavigation | None:
    context = store.load_direct(context_name)
    all_checkpoints = store.list_checkpoints(context_name)
    checkpoints = [
        checkpoint
        for checkpoint in all_checkpoints
        if not manual or not checkpoint.get("auto", False)
    ]
    projected = {
        entry.uid: entry for entry in checkpoint_picker_entries(all_checkpoints)
    }
    detail_renderer = None
    if checkpoints and show_diffs:
        detail_renderer = checkpoint_revision_detail_renderer(all_checkpoints)
    catalog = freeze_checkpoint_catalog(store) if mode == "revert" else None
    reviewed_units: dict[str, ResolvedCheckpointUnit] = {}

    def revert_review_factory(uid: str, keep: bool):
        assert catalog is not None
        unit = catalog.resolve(uid, context_name=context_name)
        reviewed_units[uid] = unit
        return revert_exact_command_review(
            context_name=context_name,
            checkpoint_uid=uid,
            keep_history=keep,
            affected_checkpoints=tuple(
                (member.context_name, member.checkpoint_uid) for member in unit.members
            ),
        )

    result = choose_history(
        [projected[checkpoint["uid"]] for checkpoint in checkpoints],
        context_name=context_name,
        mode=mode,
        initial_details_open=True,
        detail_renderer=detail_renderer,
        empty_message=(
            "No manual checkpoints for this Context yet."
            if manual
            else "No checkpoints for this Context yet."
        ),
        back_navigation=back_navigation,
        keep_history=keep_history,
        staged_checkpoint_uid=staged_checkpoint_uid,
        title=title,
        revert_review_factory=(revert_review_factory if mode == "revert" else None),
    )
    if isinstance(result, HistorySelectionReceipt):
        assert catalog is not None
        checkpoint_unit = reviewed_units.get(result.checkpoint_uid)
        if checkpoint_unit is None:
            checkpoint_unit = catalog.resolve(
                result.checkpoint_uid,
                context_name=context_name,
            )
        return ReviewedCheckpointSelection(
            context_name=context_name,
            context_uid=context.uid,
            context_digest=context_record_digest(context),
            history_digest=checkpoint_history_digest(all_checkpoints),
            checkpoint_uid=result.checkpoint_uid,
            keep_history=result.keep_history,
            checkpoint_unit=checkpoint_unit,
        )
    return result if isinstance(result, HistoryBackNavigation) else None


def browse_checkpoint_locations(
    store: MemoryStore,
    *,
    session: UpdateSession | None,
    context_locator: str | None,
    title: str,
    manual: bool = False,
    show_diffs: bool = True,
    mode: HistoryPickerMode = "log",
    keep_history: bool = False,
) -> ReviewedCheckpointSelection | None:
    """Select or resolve a Context, then browse its checkpoint transitions."""
    if manual:
        session = None
    local_names = tuple(store.list_context_names())
    update_locations = _update_locations(session)
    target_catalog = (
        tuple(context.name for context in session.target_contexts)
        if session is not None
        else ()
    )
    selectable = tuple(dict.fromkeys((*local_names, *update_locations)))
    catalog = tuple(dict.fromkeys((*local_names, *target_catalog, *update_locations)))
    if not selectable:
        raise ValueError(f"No Context locations are available for {title}.")

    def open_context_history(
        context_name: str,
        *,
        back_navigation: bool,
        staged_checkpoint_uid: str | None = None,
    ) -> ReviewedCheckpointSelection | HistoryBackNavigation | None:
        if context_name in update_locations and session is not None:
            if mode != "log":
                raise ValueError(
                    "Only ordinary local Context checkpoints can be reverted."
                )
            return choose_update_checkpoint_at_location(
                session,
                context_name,
                back_navigation=back_navigation,
                title=title,
            )
        return _browse_local_checkpoints(
            store,
            context_name,
            back_navigation=back_navigation,
            manual=manual,
            show_diffs=show_diffs,
            mode=mode,
            keep_history=keep_history,
            staged_checkpoint_uid=staged_checkpoint_uid,
            title=title,
        )

    if context_locator is not None:
        context_name = resolve_context_locator(
            context_locator,
            current=store.current_context_name(),
        )
        if context_name not in selectable:
            raise ValueError(f"Context '{context_name}' is not available for {title}.")
        result = open_context_history(context_name, back_navigation=False)
        return result if isinstance(result, ReviewedCheckpointSelection) else None

    operations_by_name: dict[str, set[str]] = defaultdict(set)
    inherited_by_name: dict[str, set[str]] = defaultdict(set)
    projected_update_operations = {
        name: identities
        for name, identities in _update_operation_ids(session).items()
        if name not in local_names
    }
    local_operations, local_inherited = _local_operation_ids(
        store,
        local_names,
        manual=manual,
    )
    for source in (local_operations, projected_update_operations):
        for name, identities in source.items():
            operations_by_name[name].update(identities)
    for name, identities in local_inherited.items():
        inherited_by_name[name].update(identities)
    annotations = _operation_annotations(
        catalog,
        operations_by_name,
        inherited_by_name,
    )

    changed_descendant_roots = tuple(
        name
        for name in catalog
        if any(location.startswith(name + "/") for location in update_locations)
    )
    selector_current = store.current_context_name()

    def load_operations(name: str) -> tuple[ContextMemoryRow, ...]:
        if name in local_names:
            context = store.load_direct(name)
            local_rows = (
                _checkpoint_version_rows
                if mode == "revert"
                else _checkpoint_operation_rows
            )(
                tuple(
                    checkpoint
                    for checkpoint in store.list_checkpoints(name)
                    if not manual or not checkpoint.get("auto", False)
                ),
                context_name=name,
                context_uid=context.uid,
            )
        else:
            local_rows = ()
        projected_rows = (
            () if name in local_names else _update_operation_rows(session, name)
        )
        return (*local_rows, *projected_rows)

    while True:
        staged_checkpoint_uid: str | None = None
        location_selection = choose_history_location(
            selectable,
            current=selector_current,
            annotations=annotations,
            title=f"{title} · SELECT A CONTEXT",
            catalog_names=catalog,
            descendant_scope_names=changed_descendant_roots,
            operation_loader=load_operations,
            select_nested_checkpoints=mode == "revert",
        )
        if location_selection is None:
            return
        if isinstance(location_selection, ContextSubtreeSelection):
            if session is None:
                raise ValueError("A saved Update is required for descendant Diff.")
            selector_current = location_selection.name
            result = choose_update_checkpoint_subtree(
                session,
                location_selection.name,
                back_navigation=True,
            )
            if result is HISTORY_BACK:
                continue
            return
        if isinstance(location_selection, CheckpointLocationSelection):
            context_name = location_selection.context_name
            staged_checkpoint_uid = location_selection.checkpoint_uid
        else:
            context_name = location_selection
        selector_current = context_name

        result = open_context_history(
            context_name,
            back_navigation=True,
            staged_checkpoint_uid=staged_checkpoint_uid,
        )
        if result is HISTORY_BACK:
            continue
        return result if isinstance(result, ReviewedCheckpointSelection) else None


def browse_diff(
    store: MemoryStore,
    *,
    session: UpdateSession | None,
    context_locator: str | None,
) -> None:
    """Open one exact Context's directional Diff details.

    A bare Diff snapshots the current Context instead of presenting the
    Profile-wide Switch tree. An explicit locator keeps the same direct
    inspection route without changing the global current pointer.
    """

    current_name = store.current_context_name()
    if context_locator is None:
        selected_locator = current_name
        if selected_locator is None:
            raise ValueError(
                "No current Context is available for Diff; pass CONTEXT or "
                "switch to one first."
            )
    else:
        selected_locator = resolve_context_locator(
            context_locator,
            current=current_name,
        )

    browse_checkpoint_locations(
        store,
        session=session,
        context_locator=selected_locator,
        title="DIFF",
    )
