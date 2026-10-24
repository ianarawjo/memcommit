"""Publish Branch archive, checkpoint and current-pointer changes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from memcommit.models.checkpoint import Checkpoint
from memcommit.core.context_navigation import record_current_context_transition
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic


def _move_record_and_history(
    source_context: Path,
    source_checkpoints: Path,
    target_context: Path,
    target_checkpoints: Path,
) -> None:
    """Move one lifecycle pair without leaving a half-moved Context."""

    source_context.rename(target_context)
    try:
        source_checkpoints.rename(target_checkpoints)
    except Exception as error:
        try:
            target_context.rename(source_context)
        except Exception as rollback_error:
            raise RuntimeError(
                "A Branch Context record moved without its history and "
                "could not be restored."
            ) from rollback_error
        raise error


def save_branch_undo(store, unit, restore_metadata, current_by_name, archives, receipt):
    """The caller retains the command, graph and affected Context locks."""
    checkpoints: list[Checkpoint] = []
    root = store.command_context_archives_dir
    name_set = {change.context_name for change in unit.changes}
    saved: list[tuple[str, Checkpoint]] = []
    moved: list[tuple[Any, Path, Path, Path]] = []
    created_archives: list[Path] = []
    undo_original_state: dict[str, object] | None = None
    state_changed = False
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Command Context archive storage is invalid.")
        for change in unit.changes:
            current = current_by_name[change.context_name]
            checkpoint = store._save_locked(
                current,
                AutoCheckpointRequest(
                    command="undo",
                    command_details={"command_restore": restore_metadata},
                ),
            )
            if checkpoint is None:
                raise RuntimeError("Branch restoration created no Undo checkpoint.")
            checkpoints.append(checkpoint)
            saved.append((change.context_name, checkpoint))
            archive = archives[change.context_name]
            archive.mkdir(mode=0o700)
            created_archives.append(archive)
            context_file = store._context_file(change.context_name)
            checkpoints_dir = store._checkpoints_dir(change.context_name)
            archived_context = archive / "context.json"
            archived_checkpoints = archive / "checkpoints"
            _move_record_and_history(
                context_file,
                checkpoints_dir,
                archived_context,
                archived_checkpoints,
            )
            moved.append(
                (
                    change,
                    archive,
                    archived_context,
                    archived_checkpoints,
                )
            )
            _write_json_atomic(
                archive / "manifest.json",
                {
                    "version": 1,
                    "command": "branch",
                    "unit_uid": unit.uid,
                    "context_uid": change.context_uid,
                    "context_name": change.context_name,
                    "checkpoint_uid": change.checkpoint_uid,
                },
            )
        with store._state_write_lock():
            state = store._read_state()
            undo_original_state = dict(state)
            if state.get("current") in name_set:
                record_current_context_transition(
                    state,
                    receipt.current_before,
                )
                store._write_state(state)
                state_changed = True
    except Exception:
        undo_rollback_error: Exception | None = None
        if state_changed and undo_original_state is not None:
            try:
                with store._state_write_lock():
                    store._write_state(undo_original_state)
            except Exception as candidate:
                undo_rollback_error = undo_rollback_error or candidate
        moved_names = {change.context_name for change, *_rest in moved}
        for (
            change,
            archive,
            archived_context,
            archived_checkpoints,
        ) in reversed(moved):
            try:
                _move_record_and_history(
                    archived_context,
                    archived_checkpoints,
                    store._context_file(change.context_name),
                    store._checkpoints_dir(change.context_name),
                )
                checkpoint = next(
                    candidate
                    for name, candidate in saved
                    if name == change.context_name
                )
                store._remove_checkpoint_uid_locked(
                    change.context_name,
                    checkpoint.uid,
                )
                manifest = archive / "manifest.json"
                if manifest.exists() and not manifest.is_symlink():
                    manifest.unlink()
                archive.rmdir()
            except Exception as candidate:
                undo_rollback_error = undo_rollback_error or candidate
        for archive_path in reversed(created_archives):
            if not archive_path.exists() or archive_path.is_symlink():
                continue
            try:
                archive_path.rmdir()
            except OSError:
                # A nonempty archive belongs to a failed
                # rollback already reported above.
                pass
        for name, checkpoint in reversed(saved):
            if name in moved_names:
                continue
            try:
                store._remove_checkpoint_uid_locked(
                    name,
                    checkpoint.uid,
                )
            except Exception as candidate:
                undo_rollback_error = undo_rollback_error or candidate
        try:
            root.rmdir()
        except OSError:
            pass
        if undo_rollback_error is not None:
            raise RuntimeError(
                "Branch Undo failed and its Context tree could "
                "not be fully rolled back."
            ) from undo_rollback_error
        raise

    return tuple(checkpoints)


def save_branch_redo(store, unit, restore_metadata, archived, receipt):
    """The caller retains the command, graph and affected Context locks."""
    checkpoints: list[Checkpoint] = []
    activated: list[tuple[Any, Path, Path, Path]] = []
    redone: list[tuple[Any, Path, Path, Path, Checkpoint]] = []
    redo_original_state: dict[str, object] | None = None
    state_changed = False
    try:
        for change in unit.changes:
            archive, _manifest, context = archived[change.context_name]
            store._context_dir(change.context_name).mkdir(
                parents=True,
                exist_ok=True,
            )
            context_file = store._context_file(change.context_name)
            checkpoints_dir = store._checkpoints_dir(change.context_name)
            archived_context = archive / "context.json"
            archived_checkpoints = archive / "checkpoints"
            _move_record_and_history(
                archived_context,
                archived_checkpoints,
                context_file,
                checkpoints_dir,
            )
            activated.append(
                (
                    change,
                    archive,
                    archived_context,
                    archived_checkpoints,
                )
            )
            checkpoint = store._save_locked(
                context,
                AutoCheckpointRequest(
                    command="redo",
                    command_details={"command_restore": restore_metadata},
                ),
            )
            if checkpoint is None:
                raise RuntimeError("Branch restoration created no Redo checkpoint.")
            checkpoints.append(checkpoint)
            redone.append(
                (
                    change,
                    archive,
                    archived_context,
                    archived_checkpoints,
                    checkpoint,
                )
            )
        with store._state_write_lock():
            state = store._read_state()
            redo_original_state = dict(state)
            if state.get("current") == receipt.current_before:
                record_current_context_transition(
                    state,
                    receipt.target_root,
                )
                store._write_state(state)
                state_changed = True
    except Exception:
        redo_rollback_error: Exception | None = None
        if state_changed and redo_original_state is not None:
            try:
                with store._state_write_lock():
                    store._write_state(redo_original_state)
            except Exception as candidate:
                redo_rollback_error = redo_rollback_error or candidate
        redone_names = {change.context_name for change, *_rest in redone}
        for (
            change,
            _archive,
            archived_context,
            archived_checkpoints,
            checkpoint,
        ) in reversed(redone):
            try:
                store._remove_checkpoint_uid_locked(
                    change.context_name,
                    checkpoint.uid,
                )
                _move_record_and_history(
                    store._context_file(change.context_name),
                    store._checkpoints_dir(change.context_name),
                    archived_context,
                    archived_checkpoints,
                )
            except Exception as candidate:
                redo_rollback_error = redo_rollback_error or candidate
        for (
            change,
            _archive,
            archived_context,
            archived_checkpoints,
        ) in reversed(activated):
            if change.context_name in redone_names:
                continue
            try:
                _move_record_and_history(
                    store._context_file(change.context_name),
                    store._checkpoints_dir(change.context_name),
                    archived_context,
                    archived_checkpoints,
                )
            except Exception as candidate:
                redo_rollback_error = redo_rollback_error or candidate
        if redo_rollback_error is not None:
            raise RuntimeError(
                "Branch Redo failed and its Context tree could "
                "not be fully rolled back."
            ) from redo_rollback_error
        raise
    for change, archive, *_rest in redone:
        manifest = archive / "manifest.json"
        manifest.unlink()
        archive.rmdir()
    try:
        store.command_context_archives_dir.rmdir()
    except OSError:
        pass

    return tuple(checkpoints)
