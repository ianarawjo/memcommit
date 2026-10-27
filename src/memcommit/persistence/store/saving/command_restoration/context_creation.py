"""Publish Context creation archive, checkpoint and current-pointer changes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from memcommit.models.checkpoint import Checkpoint
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store.infrastructure.atomic_io import (
    _write_json_atomic,
    _write_bytes_atomic,
)


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
                "A Context creation Context record moved without its history and "
                "could not be restored."
            ) from rollback_error
        raise error


def save_context_creation_undo(
    store,
    unit,
    restore_metadata,
    current_by_name,
    archives,
    *,
    current_before,
    companion_changes=(),
):
    """The caller retains the command, graph and affected Context locks."""
    companion_writes = []
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
                raise RuntimeError(
                    "Context creation restoration created no Undo checkpoint."
                )
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
                    "command": unit.command,
                    "unit_uid": unit.uid,
                    "context_uid": change.context_uid,
                    "context_name": change.context_name,
                    "checkpoint_uid": change.checkpoint_uid,
                    **(
                        {"creation_batch": True}
                        if any(
                            "context_creation_batch" in details
                            for details in unit.checkpoint_command_details
                        )
                        else {}
                    ),
                },
            )
        if companion_changes:
            companion_archive = (
                archives[unit.changes[0].context_name] / "companion-records.json"
            )
            _write_json_atomic(
                companion_archive,
                [
                    {
                        "path": path.relative_to(store.store_dir).as_posix(),
                        "before": before,
                        "after": after,
                    }
                    for path, before, after in companion_changes
                ],
            )
        for path, before, after in companion_changes:
            companion_writes.append((path, before))
            _write_companion_record(path, after)
        with store._state_write_lock():
            state = store._read_state()
            undo_original_state = dict(state)
            if state.get("current") in name_set:
                state["current"] = current_before
                store._write_state(state)
                state_changed = True
    except Exception:
        undo_rollback_error = None
        for path, before in reversed(companion_writes):
            try:
                _write_companion_record(path, before)
            except Exception as error:
                undo_rollback_error = undo_rollback_error or error
        if companion_changes:
            (archives[unit.changes[0].context_name] / "companion-records.json").unlink(
                missing_ok=True
            )
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
                "Context creation Undo failed and its Context tree could "
                "not be fully rolled back."
            ) from undo_rollback_error
        raise

    return tuple(checkpoints)


def save_context_creation_redo(
    store,
    unit,
    restore_metadata,
    archived,
    *,
    current_before,
    current_after,
    companion_changes=(),
):
    """The caller retains the command, graph and affected Context locks."""
    companion_writes = []
    checkpoints: list[Checkpoint] = []
    activated: list[tuple[Any, Path, Path, Path]] = []
    redone: list[tuple[Any, Path, Path, Path, Checkpoint]] = []
    redo_original_state: dict[str, object] | None = None
    state_changed = False
    consumed_files = []
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
                raise RuntimeError(
                    "Context creation restoration created no Redo checkpoint."
                )
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
        for path, before, after in companion_changes:
            companion_writes.append((path, before))
            _write_companion_record(path, after)
        with store._state_write_lock():
            state = store._read_state()
            redo_original_state = dict(state)
            if state.get("current") == current_before:
                state["current"] = current_after
                store._write_state(state)
                state_changed = True
        for _change, archive, *_rest in redone:
            for name in ("manifest.json", "companion-records.json"):
                path = archive / name
                if path.exists():
                    consumed_files.append((path, path.read_bytes()))
                    path.unlink()
            archive.rmdir()
    except Exception:
        redo_rollback_error = None
        for path, content in consumed_files:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                _write_bytes_atomic(path, content)
            except Exception as error:
                redo_rollback_error = redo_rollback_error or error
        for path, before in reversed(companion_writes):
            try:
                _write_companion_record(path, before)
            except Exception as error:
                redo_rollback_error = redo_rollback_error or error
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
                "Context creation Redo failed and its Context tree could "
                "not be fully rolled back."
            ) from redo_rollback_error
        raise
    try:
        store.command_context_archives_dir.rmdir()
    except OSError:
        pass

    return tuple(checkpoints)


def _write_companion_record(path, content):
    if content is None:
        path.unlink(missing_ok=True)
    else:
        _write_bytes_atomic(path, content.encode("utf-8"))
