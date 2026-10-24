"""Publish prepared Merge Context images and archive lifecycles."""

from __future__ import annotations


from memcommit.models.checkpoint import Checkpoint
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.infrastructure.atomic_io import (
    _write_json_atomic,
    _write_bytes_atomic,
)


def save_merge_undo(
    store,
    unit,
    restore_metadata,
    current_by_name,
    original_bytes,
    updated_changes,
    created_changes,
):
    """The caller retains the command, graph and affected Context locks."""
    checkpoints: list[Checkpoint] = []
    updated_written: list[tuple[str, Checkpoint]] = []
    created_saved: list[tuple[str, Checkpoint]] = []
    moved: list[tuple[object, object, object, object]] = []
    try:
        for change in updated_changes:
            assert change.before is not None
            restored = store._context_for_restoration(
                change.before,
                context_uid=change.context_uid,
                context_name=change.context_name,
            )
            checkpoint = store._save_locked(
                restored,
                AutoCheckpointRequest(
                    command="undo",
                    command_details={"command_restore": restore_metadata},
                ),
            )
            if checkpoint is None:
                raise RuntimeError("Merge restoration created no Undo checkpoint.")
            checkpoints.append(checkpoint)
            updated_written.append((change.context_name, checkpoint))

        for change in created_changes:
            current = current_by_name[change.context_name]
            checkpoint = store._save_locked(
                current,
                AutoCheckpointRequest(
                    command="undo",
                    command_details={"command_restore": restore_metadata},
                ),
            )
            if checkpoint is None:
                raise RuntimeError("Merge restoration created no Undo checkpoint.")
            checkpoints.append(checkpoint)
            created_saved.append((change.context_name, checkpoint))
            archive = store._command_context_archive_path(change.checkpoint_uid)
            root = archive.parent
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if root.is_symlink() or not root.is_dir():
                raise ValueError("Command Context archive storage is invalid.")
            if archive.exists() or archive.is_symlink():
                raise ConcurrentContextUpdateError(
                    "A Merge command archive already exists."
                )
            archive.mkdir(mode=0o700)
            context_file = store._context_file(change.context_name)
            checkpoints_dir = store._checkpoints_dir(change.context_name)
            archived_context = archive / "context.json"
            archived_checkpoints = archive / "checkpoints"
            context_file.rename(archived_context)
            checkpoints_dir.rename(archived_checkpoints)
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
                    "command": unit.command,
                    "unit_uid": unit.uid,
                    "context_uid": change.context_uid,
                    "context_name": change.context_name,
                    "checkpoint_uid": change.checkpoint_uid,
                },
            )
    except Exception:
        rollback_error: Exception | None = None
        moved_names = {change.context_name for change, *_rest in moved}
        for (
            change,
            archive,
            archived_context,
            archived_checkpoints,
        ) in reversed(moved):
            try:
                archived_checkpoints.rename(store._checkpoints_dir(change.context_name))
                archived_context.rename(store._context_file(change.context_name))
                checkpoint = next(
                    checkpoint
                    for name, checkpoint in created_saved
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
                rollback_error = rollback_error or candidate
        for name, checkpoint in reversed(created_saved):
            if name in moved_names:
                continue
            try:
                store._remove_checkpoint_uid_locked(
                    name,
                    checkpoint.uid,
                )
            except Exception as candidate:
                rollback_error = rollback_error or candidate
        for name, checkpoint in reversed(updated_written):
            try:
                _write_bytes_atomic(
                    store._context_file(name),
                    original_bytes[name],
                )
                store._remove_checkpoint_uid_locked(
                    name,
                    checkpoint.uid,
                )
            except Exception as candidate:
                rollback_error = rollback_error or candidate
        if rollback_error is not None:
            raise RuntimeError(
                "Merge Undo failed and its Context tree could not be fully rolled back."
            ) from rollback_error
        raise

    return tuple(checkpoints)


def save_merge_redo(
    store,
    unit,
    restore_metadata,
    current_by_name,
    original_bytes,
    updated_changes,
    created_changes,
    archives,
):
    """The caller retains the command, graph and affected Context locks."""
    checkpoints: list[Checkpoint] = []
    updated_written: list[tuple[str, Checkpoint]] = []
    activated: list[tuple[object, object, object, object]] = []
    moved: list[tuple[object, object, object, object, Checkpoint]] = []
    try:
        for change in updated_changes:
            assert change.after is not None
            restored = store._context_for_restoration(
                change.after,
                context_uid=change.context_uid,
                context_name=change.context_name,
            )
            checkpoint = store._save_locked(
                restored,
                AutoCheckpointRequest(
                    command="redo",
                    command_details={"command_restore": restore_metadata},
                ),
            )
            if checkpoint is None:
                raise RuntimeError("Merge restoration created no Redo checkpoint.")
            checkpoints.append(checkpoint)
            updated_written.append((change.context_name, checkpoint))

        for change in created_changes:
            archive, _manifest, archived = archives[change.context_name]
            store._assert_context_storage_available(change.context_name)
            store._context_dir(change.context_name).mkdir(
                parents=True,
                exist_ok=True,
            )
            context_file = store._context_file(change.context_name)
            checkpoints_dir = store._checkpoints_dir(change.context_name)
            archived_context = archive / "context.json"
            archived_checkpoints = archive / "checkpoints"
            archived_context.rename(context_file)
            archived_checkpoints.rename(checkpoints_dir)
            activated.append(
                (
                    change,
                    archive,
                    archived_context,
                    archived_checkpoints,
                )
            )
            checkpoint = store._save_locked(
                archived,
                AutoCheckpointRequest(
                    command="redo",
                    command_details={"command_restore": restore_metadata},
                ),
            )
            if checkpoint is None:
                raise RuntimeError("Merge restoration created no Redo checkpoint.")
            checkpoints.append(checkpoint)
            moved.append(
                (
                    change,
                    archive,
                    archived_context,
                    archived_checkpoints,
                    checkpoint,
                )
            )
    except Exception:
        rollback_error: Exception | None = None
        moved_names = {change.context_name for change, *_rest in moved}
        for (
            change,
            archive,
            archived_context,
            archived_checkpoints,
            checkpoint,
        ) in reversed(moved):
            try:
                store._remove_checkpoint_uid_locked(
                    change.context_name,
                    checkpoint.uid,
                )
                store._checkpoints_dir(change.context_name).rename(archived_checkpoints)
                store._context_file(change.context_name).rename(archived_context)
            except Exception as candidate:
                rollback_error = rollback_error or candidate
        for (
            change,
            archive,
            archived_context,
            archived_checkpoints,
        ) in reversed(activated):
            if change.context_name in moved_names:
                continue
            try:
                store._checkpoints_dir(change.context_name).rename(archived_checkpoints)
                store._context_file(change.context_name).rename(archived_context)
            except Exception as candidate:
                rollback_error = rollback_error or candidate
        for name, checkpoint in reversed(updated_written):
            try:
                _write_bytes_atomic(
                    store._context_file(name),
                    original_bytes[name],
                )
                store._remove_checkpoint_uid_locked(
                    name,
                    checkpoint.uid,
                )
            except Exception as candidate:
                rollback_error = rollback_error or candidate
        if rollback_error is not None:
            raise RuntimeError(
                "Merge Redo failed and its Context tree could not be fully rolled back."
            ) from rollback_error
        raise
    for change, archive, *_rest in moved:
        manifest = archive / "manifest.json"
        manifest.unlink()
        archive.rmdir()
    try:
        store.command_context_archives_dir.rmdir()
    except OSError:
        pass

    return tuple(checkpoints)
