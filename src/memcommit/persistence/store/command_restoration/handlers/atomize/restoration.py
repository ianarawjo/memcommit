"""Coordinate exact Atomize Save As restoration under one lock boundary."""

from __future__ import annotations

import copy
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator
import uuid

from memcommit.core.context import AutoCheckpoint, Checkpoint, Context
from memcommit.core.context_navigation import record_current_context_transition

from ....context_memory.models import ConcurrentContextUpdateError
from ....context_memory.records import context_record_digest
from ....infrastructure.atomic_io import _write_json_atomic
from ...compensation import CompensationStack
from .preparation import load_undo_context, prepare_redo, prepare_undo
from .records import AtomizeArchiveManifest, load_creation_receipt

if TYPE_CHECKING:
    from memcommit.application.capabilities.command_recovery.model import (
        CommandRestoreResult,
        ContextCommandUnit,
    )
    from memcommit.persistence.store import MemoryStore


class _AtomizeRestorationMixin:
    """Retain the Store entry point; direction-specific workflows own execution."""

    def _restore_atomize_context_creation_command_locked(
        self, unit: ContextCommandUnit, direction: str
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
        auto_checkpoint = AutoCheckpoint(
            command=direction,
            args={
                "command_restore": command_restore_metadata(
                    receipt_uid=receipt_uid,
                    direction=direction,
                    unit=unit,
                )
            },
            description=f"{direction.title()} command 'mem atomize' [{receipt_uid[:8]}]",
        )
        restore = _undo_locked if direction == "undo" else _redo_locked
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(unit.changes[0].context_name):
                checkpoint = restore(self, unit, auto_checkpoint)
        return CommandRestoreResult(
            unit=unit,
            direction=direction,
            receipt_uid=receipt_uid,
            checkpoints=(checkpoint,),
        )


@contextmanager
def _session_locks(
    store: MemoryStore, source_uid: str, output_uid: str
) -> Iterator[None]:
    with ExitStack() as locks:
        for uid in sorted({source_uid, output_uid}):
            locks.enter_context(store._atomize_session_write_lock(uid))
        yield


def _undo_locked(
    store: MemoryStore, unit: ContextCommandUnit, auto_checkpoint: AutoCheckpoint
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
        # The final state lock outlives compensation, including failures during
        # cleanup. Otherwise rollback could overwrite a concurrent navigation.
        with ExitStack() as final_locks, CompensationStack() as compensation:
            root_existed = archive.parent.exists()
            archive.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if archive.parent.is_symlink() or not archive.parent.is_dir():
                raise ValueError("Command Context archive storage is invalid.")
            if not root_existed:
                compensation.defer(_remove_empty_directory, archive.parent)
            archive.mkdir(mode=0o700)
            compensation.defer(archive.rmdir)
            checkpoint = _save_checkpoint(store, current, auto_checkpoint, compensation)
            compensation.move(
                store._context_file(change.context_name), archive / "context.json"
            )
            compensation.move(
                store._checkpoints_dir(change.context_name), archive / "checkpoints"
            )
            compensation.move(
                store._atomize_analysis_path(change.context_uid),
                archive / "atomize-analysis.json",
            )
            manifest_path = archive / "manifest.json"
            compensation.defer(manifest_path.unlink, missing_ok=True)
            _write_json_atomic(manifest_path, prepared.manifest.to_dict())
            if prepared.workbench_after is not None:
                compensation.defer(
                    store._save_atomize_workbench_locked, prepared.workbench_before
                )
                store._save_atomize_workbench_locked(prepared.workbench_after)
            _switch_current(
                store,
                final_locks,
                compensation,
                expected=change.context_name,
                target=receipt.current_before,
            )
        return checkpoint


def _redo_locked(
    store: MemoryStore, unit: ContextCommandUnit, auto_checkpoint: AutoCheckpoint
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
        with ExitStack() as final_locks, CompensationStack() as compensation:
            context_dir = store._context_dir(change.context_name)
            if not context_dir.exists():
                context_dir.mkdir(parents=True)
                compensation.defer(store._prune_empty_namespace_dirs, context_dir)
            compensation.move(
                archive / "context.json", store._context_file(change.context_name)
            )
            compensation.move(
                archive / "checkpoints", store._checkpoints_dir(change.context_name)
            )
            compensation.move(
                archive / "atomize-analysis.json",
                store._atomize_analysis_path(change.context_uid),
            )
            checkpoint = _save_checkpoint(
                store, prepared.context, auto_checkpoint, compensation
            )
            if prepared.workbench_after is not None:
                compensation.defer(
                    store._save_atomize_workbench_locked, prepared.workbench_before
                )
                store._save_atomize_workbench_locked(prepared.workbench_after)
            _switch_current(
                store,
                final_locks,
                compensation,
                expected=manifest.current_before,
                target=change.context_name,
            )
            # Consuming the archive is part of Redo: a cleanup failure restores
            # its manifest and all prior changes so the same Redo can be retried.
            manifest_path = archive / "manifest.json"
            compensation.defer(_write_json_atomic, manifest_path, raw_manifest)
            manifest_path.unlink()
            archive.rmdir()
        _remove_empty_directory(archive.parent)
        return checkpoint


def _save_checkpoint(
    store: MemoryStore,
    context: Context,
    auto_checkpoint: AutoCheckpoint,
    compensation: CompensationStack,
) -> Checkpoint:
    checkpoint = store._save_locked(
        context,
        auto_checkpoint,
        expected_context_digest=context_record_digest(context),
    )
    if checkpoint is None:
        raise RuntimeError(
            f"Atomize restoration created no {auto_checkpoint.command.title()} checkpoint."
        )
    compensation.defer(
        store._remove_checkpoint_uid_locked, context.name, checkpoint.uid
    )
    return checkpoint


def _switch_current(
    store: MemoryStore,
    locks: ExitStack,
    compensation: CompensationStack,
    *,
    expected: str | None,
    target: str | None,
) -> None:
    locks.enter_context(store._state_write_lock())
    state = store._read_state()
    if state.get("current") == expected:
        # Register before writing: a writer may report an error after replacing
        # its file. The lock is still held while this inverse runs.
        compensation.defer(store._write_state, copy.deepcopy(state))
        record_current_context_transition(state, target)
        store._write_state(state)


def _remove_empty_directory(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        # Shared parents can contain another command archive or namespace.
        pass
