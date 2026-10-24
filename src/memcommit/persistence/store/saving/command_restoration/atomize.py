"""Publish prepared Atomize restoration and compensate every completed write."""

from __future__ import annotations

import copy
from contextlib import ExitStack
from pathlib import Path
from typing import TYPE_CHECKING

from memcommit.models.context import Context
from memcommit.models.checkpoint import Checkpoint
from memcommit.core.context_navigation import record_current_context_transition
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic
from .compensation import CompensationStack

if TYPE_CHECKING:
    from memcommit.persistence.store import MemoryStore


def save_atomize_undo(store, change, prepared, archive, auto_checkpoint, receipt):
    """The caller retains command, graph, Context and Atomize session locks."""
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
        checkpoint = _save_checkpoint(
            store, prepared.context, auto_checkpoint, compensation
        )
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


def save_atomize_redo(
    store, change, prepared, archive, raw_manifest, auto_checkpoint, manifest
):
    """The caller retains command, graph, Context and Atomize session locks."""
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
    auto_checkpoint: AutoCheckpointRequest,
    compensation: CompensationStack,
) -> Checkpoint:
    checkpoint = store._save_locked(
        context,
        auto_checkpoint,
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
