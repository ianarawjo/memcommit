"""Save prepared Sever Context/archive and review-session versions."""

from __future__ import annotations


from memcommit.core.context_navigation import record_current_context_transition
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic


def save_sever_undo(
    store,
    change,
    current,
    restore_metadata,
    sessions,
    session,
    reviewing,
    session_before_digest,
    reviewing_digest,
    *,
    manifest,
):
    """The caller retains the command, graph and Context locks."""
    checkpoint = store._save_locked(
        current,
        AutoCheckpointRequest(
            command="undo",
            command_details={"command_restore": restore_metadata},
        ),
    )
    if checkpoint is None:
        raise RuntimeError("Sever restoration created no Undo checkpoint.")
    archive = store._command_context_archive_path(change.checkpoint_uid)
    root = archive.parent
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Command Context archive storage is invalid.")
    if archive.exists() or archive.is_symlink():
        raise ConcurrentContextUpdateError("A Sever command archive already exists.")
    archive.mkdir(mode=0o700)
    context_file = store._context_file(change.context_name)
    checkpoints_dir = store._checkpoints_dir(change.context_name)
    archived_context = archive / "context.json"
    archived_checkpoints = archive / "checkpoints"
    moved = False
    session_saved = False
    try:
        context_file.rename(archived_context)
        checkpoints_dir.rename(archived_checkpoints)
        moved = True
        _write_json_atomic(
            archive / "manifest.json",
            manifest,
        )
        sessions.save(
            reviewing,
            expected_digest=session_before_digest,
        )
        session_saved = True
        with store._state_write_lock():
            state = store._read_state()
            if state.get("current") == change.context_name:
                record_current_context_transition(state, None)
                store._write_state(state)
    except Exception:
        if session_saved:
            sessions.save(
                session,
                expected_digest=reviewing_digest,
            )
        if moved:
            archived_checkpoints.rename(checkpoints_dir)
            archived_context.rename(context_file)
            store._remove_checkpoint_uid_locked(
                change.context_name,
                checkpoint.uid,
            )
        manifest_path = archive / "manifest.json"
        if manifest_path.exists() and not manifest_path.is_symlink():
            manifest_path.unlink()
        try:
            archive.rmdir()
            root.rmdir()
        except OSError:
            pass
        raise

    return checkpoint


def save_sever_redo(
    store,
    change,
    archive,
    archived_context,
    restore_metadata,
    sessions,
    applied,
    session_before_digest,
):
    """The caller retains the command, graph and Context locks."""
    checkpoint = None
    store._assert_context_storage_available(change.context_name)
    context_dir = store._context_dir(change.context_name)
    context_dir.mkdir(parents=True, exist_ok=True)
    context_file = store._context_file(change.context_name)
    checkpoints_dir = store._checkpoints_dir(change.context_name)
    archived_context_file = archive / "context.json"
    archived_checkpoints = archive / "checkpoints"
    moved = False
    try:
        archived_context_file.rename(context_file)
        archived_checkpoints.rename(checkpoints_dir)
        moved = True
        checkpoint = store._save_locked(
            archived_context,
            AutoCheckpointRequest(
                command="redo",
                command_details={"command_restore": restore_metadata},
            ),
        )
        if checkpoint is None:
            raise RuntimeError("Sever restoration created no Redo checkpoint.")
        sessions.save(
            applied,
            expected_digest=session_before_digest,
        )
    except Exception:
        if moved:
            if checkpoint is not None:
                store._remove_checkpoint_uid_locked(
                    change.context_name,
                    checkpoint.uid,
                )
            checkpoints_dir.rename(archived_checkpoints)
            context_file.rename(archived_context_file)
        raise
    manifest_path = archive / "manifest.json"
    manifest_path.unlink()
    archive.rmdir()
    try:
        archive.parent.rmdir()
    except OSError:
        pass

    return checkpoint
