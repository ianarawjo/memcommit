"""Prepare exact Atomize restoration under its original lock boundary."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING, Iterator
import uuid

from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.checkpoint import Checkpoint
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.loading.atomize_archive_records import (
    AtomizeArchiveManifest,
    load_creation_receipt,
)
from memcommit.persistence.store.saving.command_restoration.atomize import (
    save_atomize_undo,
    save_atomize_redo,
)
from .preparation import load_undo_context, prepare_redo, prepare_undo

if TYPE_CHECKING:
    from memcommit.application.capabilities.command_recovery.model import (
        CommandRestoreResult,
        ContextCommandUnit,
    )
    from memcommit.persistence.store import ProfileStore


def restore_atomize_context_creation(
    store, unit: ContextCommandUnit, direction: str
) -> CommandRestoreResult:
    from memcommit.application.capabilities.command_recovery.model import (
        CommandRestoreResult,
    )
    from memcommit.application.capabilities.command_recovery.restore_receipt import (
        command_restore_metadata,
    )

    if direction not in {"undo", "redo"}:
        raise ValueError("Command restoration direction must be undo or redo.")
    if (
        unit.command != "atomize"
        or len(unit.changes) != 1
        or unit.changes[0].before is not None
        or unit.changes[0].after is None
    ):
        raise ValueError(
            "Only an exact Atomize Save As creation can use lifecycle restoration."
        )
    receipt_uid = str(uuid.uuid4())
    auto_checkpoint = AutoCheckpointRequest(
        command=direction,
        command_details={
            "command_restore": command_restore_metadata(
                receipt_uid=receipt_uid,
                direction=direction,
                unit=unit,
            )
        },
    )
    restore = _undo_locked if direction == "undo" else _redo_locked
    with store._context_graph_lock(exclusive=True):
        with store._context_write_lock(unit.changes[0].context_name):
            checkpoint = restore(store, unit, auto_checkpoint)
    return CommandRestoreResult(
        unit=unit,
        direction=direction,
        receipt_uid=receipt_uid,
        checkpoints=(checkpoint,),
    )


@contextmanager
def _session_locks(
    store: ProfileStore, source_uid: str, output_uid: str
) -> Iterator[None]:
    with ExitStack() as locks:
        for uid in sorted({source_uid, output_uid}):
            locks.enter_context(store._atomize_session_write_lock(uid))
        yield


def _undo_locked(
    store: ProfileStore, unit: ContextCommandUnit, auto_checkpoint: AutoCheckpointRequest
) -> Checkpoint:
    change = unit.changes[0]
    current = load_undo_context(store, change)
    receipt = load_creation_receipt(store.list_checkpoints(change.context_name), change)
    with _session_locks(store, receipt.source_context_uid, change.context_uid):
        prepared = prepare_undo(store, unit, current, receipt)
        archive = store._command_context_archive_path(change.checkpoint_uid)
        if archive.exists() or archive.is_symlink():
            raise ConcurrentContextUpdateError(
                "An Atomize command archive already exists."
            )
        return save_atomize_undo(
            store, change, prepared, archive, auto_checkpoint, receipt
        )


def _redo_locked(
    store: ProfileStore, unit: ContextCommandUnit, auto_checkpoint: AutoCheckpointRequest
) -> Checkpoint:
    change = unit.changes[0]
    if store.context_exists(change.context_name):
        raise ConcurrentContextUpdateError(
            f"Affected Context '{change.context_name}' already exists."
        )
    archive, raw_manifest, archived_context, entries = (
        store._load_command_context_archive(change.checkpoint_uid)
    )
    manifest = AtomizeArchiveManifest.from_dict(raw_manifest)
    receipt = load_creation_receipt(entries, change)
    with _session_locks(store, manifest.source_context_uid, change.context_uid):
        prepared = prepare_redo(
            store, unit, archive, archived_context, manifest, receipt
        )
        return save_atomize_redo(
            store, change, prepared, archive, raw_manifest, auto_checkpoint, manifest
        )
