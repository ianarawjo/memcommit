"""Shared location-first browser for Diff, Log, and Revert checkpoints."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from memcommit.commands.checkpoint_diff import (
    checkpoint_diff_detail_renderer,
    checkpoint_restore_detail_renderer,
)
from memcommit.commands.context_picker import (
    ContextMemoryRow,
    ContextSubtreeSelection,
)
from memcommit.commands.history_location_picker import choose_history_location
from memcommit.commands.history_picker import (
    HISTORY_BACK,
    HistoryBackNavigation,
    HistoryPickerMode,
    HistorySelectionReceipt,
    choose_history,
)
from memcommit.commands.history_present import checkpoint_picker_entries
from memcommit.commands.update_checkpoint_history import (
    choose_update_checkpoint_at_location,
    choose_update_checkpoint_subtree,
)
from memcommit.context_locator import resolve_context_locator
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


def _update_locations(session: UpdateSession | None) -> tuple[str, ...]:
    if session is None:
        return ()
    return tuple(
        dict.fromkeys(operation.owner_context_name for operation in session.operations)
    )


def _checkpoint_operation_identity(checkpoint: Mapping[str, object]) -> str | None:
    """Return the command-unit identity represented by one checkpoint file."""

    command = checkpoint.get("command")
    if command == "init":
        # Init is the baseline for later transitions, not a Diff operation.
        return None
    uid = checkpoint.get("uid")
    if not isinstance(uid, str) or not uid:
        return None
    args = checkpoint.get("args")
    args = args if isinstance(args, dict) else {}
    if command == "update":
        session_uid = args.get("update_session_uid")
        operation_digest = args.get("operation_digest")
        if (
            isinstance(session_uid, str)
            and session_uid
            and isinstance(operation_digest, str)
            and operation_digest
        ):
            return f"update:{session_uid}:{operation_digest}"
    if command in {"undo", "redo"}:
        restore = args.get("command_restore")
        if isinstance(restore, dict):
            receipt_uid = restore.get("receipt_uid")
            if isinstance(receipt_uid, str) and receipt_uid:
                return f"restore:{receipt_uid}"
    return f"checkpoint:{uid}"


def _local_operation_ids(
    store: MemoryStore,
    names: Sequence[str],
    *,
    manual: bool = False,
) -> dict[str, set[str]]:
    operations: dict[str, set[str]] = {}
    for name in names:
        checkpoints = [
            checkpoint
            for checkpoint in store.list_checkpoints(name)
            if not manual or not checkpoint.get("auto", False)
        ]
        operations[name] = set(
            identity
            for checkpoint in checkpoints
            if (identity := _checkpoint_operation_identity(checkpoint)) is not None
        )
    return operations


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
) -> dict[str, str]:
    """Count distinct direct and descendant command units for every row."""

    annotations: dict[str, str] = {}
    for name in catalog:
        direct = operations_by_name.get(name, set())
        prefix = name + "/"
        descendants: set[str] = set()
        for owner, identities in operations_by_name.items():
            if owner.startswith(prefix):
                descendants.update(identities)
        annotations[name] = (
            f"{len(direct)} direct · {len(descendants)} descendant "
            f"operation{'s' if len(descendants) != 1 else ''}"
        )
    return annotations


def _checkpoint_operation_rows(
    checkpoints: Sequence[Mapping[str, object]],
) -> tuple[ContextMemoryRow, ...]:
    """Project direct operations plus a non-counted creation boundary."""

    rows: list[ContextMemoryRow] = []
    seen: set[str] = set()
    for checkpoint in checkpoints:
        command = str(checkpoint.get("command") or "checkpoint")
        timestamp = str(checkpoint.get("timestamp") or "")[:16].replace("T", " ")
        uid = str(checkpoint.get("uid") or "")[:8]
        description = str(
            checkpoint.get("description")
            or checkpoint.get("message")
            or "(no description)"
        )
        detail = f"{timestamp} · {uid} · {' '.join(description.split())}"
        if command == "init":
            args = checkpoint.get("args")
            atomize_created = (
                isinstance(args, Mapping)
                and isinstance(args.get("source_analysis_uid"), str)
                and bool(args["source_analysis_uid"])
            )
            # Creation is a lifecycle boundary rather than another operation,
            # so it remains outside direct/descendant counts. The second badge
            # names Atomize only when its durable init receipt proves that
            # provenance; an oldest retained checkpoint is not enough proof.
            rows.append(
                ContextMemoryRow(
                    "created",
                    ("[atomize] " if atomize_created else "") + detail,
                    style="report-neutral",
                )
            )
            continue
        identity = _checkpoint_operation_identity(checkpoint)
        if identity is None or identity in seen:
            continue
        seen.add(identity)
        rows.append(
            ContextMemoryRow(
                command,
                detail,
                style="report-neutral",
            )
        )
    return tuple(rows)


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
    checkpoint = next(
        (
            receipt.checkpoint_uid[:8]
            for receipt in session.application.checkpoints
            if receipt.context_name == name
        ),
        "(not created)",
    )
    rows = [
        ContextMemoryRow(
            "update",
            f"{operation_count} Memory changes · checkpoint {checkpoint}",
            style="report-neutral",
        )
    ]
    if session.status == "undone":
        rows.insert(
            0,
            ContextMemoryRow(
                "undo",
                "restored the retained Update operation",
                style="report-neutral",
            ),
        )
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
        detail_renderer = (
            checkpoint_restore_detail_renderer(
                context.to_dict(),
                all_checkpoints,
            )
            if mode == "revert"
            else checkpoint_diff_detail_renderer(all_checkpoints)
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
    )
    if isinstance(result, HistorySelectionReceipt):
        return ReviewedCheckpointSelection(
            context_name=context_name,
            context_uid=context.uid,
            context_digest=context_record_digest(context),
            history_digest=checkpoint_history_digest(all_checkpoints),
            checkpoint_uid=result.checkpoint_uid,
            keep_history=result.keep_history,
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

    operations_by_name: dict[str, set[str]] = defaultdict(set)
    projected_update_operations = {
        name: identities
        for name, identities in _update_operation_ids(session).items()
        if name not in local_names
    }
    for source in (
        _local_operation_ids(store, local_names, manual=manual),
        projected_update_operations,
    ):
        for name, identities in source.items():
            operations_by_name[name].update(identities)
    annotations = _operation_annotations(catalog, operations_by_name)

    changed_descendant_roots = tuple(
        name
        for name in catalog
        if any(location.startswith(name + "/") for location in update_locations)
    )
    selector_current = store.current_context_name()

    def load_operations(name: str) -> tuple[ContextMemoryRow, ...]:
        local_rows = (
            _checkpoint_operation_rows(
                tuple(
                    checkpoint
                    for checkpoint in store.list_checkpoints(name)
                    if not manual or not checkpoint.get("auto", False)
                )
            )
            if name in local_names
            else ()
        )
        projected_rows = (
            () if name in local_names else _update_operation_rows(session, name)
        )
        return (*local_rows, *projected_rows)

    while True:
        if context_locator is None:
            location_selection = choose_history_location(
                selectable,
                current=selector_current,
                annotations=annotations,
                title=f"{title} · SELECT A CONTEXT",
                catalog_names=catalog,
                descendant_scope_names=changed_descendant_roots,
                operation_loader=load_operations,
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
            context_name = location_selection
            selector_current = context_name
        else:
            context_name = resolve_context_locator(
                context_locator,
                current=store.current_context_name(),
            )
            if context_name not in selectable:
                raise ValueError(
                    f"Context '{context_name}' is not available for {title}."
                )

        if context_name in update_locations and session is not None:
            if mode != "log":
                raise ValueError(
                    "Only ordinary local Context checkpoints can be reverted."
                )
            result = choose_update_checkpoint_at_location(
                session,
                context_name,
                back_navigation=context_locator is None,
            )
        else:
            result = _browse_local_checkpoints(
                store,
                context_name,
                back_navigation=context_locator is None,
                manual=manual,
                show_diffs=show_diffs,
                mode=mode,
                keep_history=keep_history,
            )
        if result is HISTORY_BACK and context_locator is None:
            continue
        return result if isinstance(result, ReviewedCheckpointSelection) else None


def browse_diff(
    store: MemoryStore,
    *,
    session: UpdateSession | None,
    context_locator: str | None,
) -> None:
    """Open the common location browser with directional Diff details."""

    browse_checkpoint_locations(
        store,
        session=session,
        context_locator=context_locator,
        title="DIFF",
    )
