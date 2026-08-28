"""Restore exact Merge-created Contexts."""

from __future__ import annotations
import uuid
from memcommit.core.context import AutoCheckpoint, Checkpoint, Context
from ...context_memory.models import ConcurrentContextUpdateError
from ...context_memory.records import (
    context_record_digest,
)
from ...infrastructure.atomic_io import (
    _write_bytes_atomic,
    _write_json_atomic,
)


class _MergeRestorationMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    def _restore_merge_context_creation_command_locked(self, unit, direction: str):
        """Atomically restore a Merge across updated and created Contexts.

        Created descendants move into the same private, validated lifecycle
        archive used by command history. Updated Contexts are restored in
        place. Every member receives the same restoration receipt, so neither
        a partial tree nor an incomplete redo can enter the global stack.
        """
        from memcommit.application.capabilities.retained_history.command_history import (
            CommandRestoreResult,
            command_restore_metadata,
        )

        if (
            unit.command != "merge"
            or not unit.changes
            or any(change.after is None for change in unit.changes)
            or not any(change.before is None for change in unit.changes)
        ):
            raise ValueError(
                "Merge lifecycle restoration requires one complete mixed command unit."
            )
        names = tuple(change.context_name for change in unit.changes)
        receipt_uid = str(uuid.uuid4())
        restore_metadata = command_restore_metadata(
            receipt_uid=receipt_uid,
            direction=direction,
            unit=unit,
        )
        created_changes = tuple(
            change for change in unit.changes if change.before is None
        )
        updated_changes = tuple(
            change for change in unit.changes if change.before is not None
        )
        checkpoints: list[Checkpoint] = []

        with self._context_graph_lock(exclusive=True):
            with self._context_write_locks(names):
                if direction == "undo":
                    current_by_name: dict[str, Context] = {}
                    original_bytes: dict[str, bytes] = {}
                    for change in unit.changes:
                        try:
                            current = self.load_direct(change.context_name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' "
                                "no longer exists."
                            ) from error
                        assert change.after is not None
                        if current.uid != change.context_uid or context_record_digest(
                            current
                        ) != context_record_digest(change.after):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' changed "
                                "after the Merge selected for undo."
                            )
                        if change.before is None:
                            self._assert_context_deletion_allowed(current)
                        current_by_name[change.context_name] = current
                        original_bytes[change.context_name] = self._context_file(
                            change.context_name
                        ).read_bytes()

                    updated_written: list[tuple[str, Checkpoint]] = []
                    created_saved: list[tuple[str, Checkpoint]] = []
                    moved: list[tuple[object, object, object, object]] = []
                    try:
                        for change in updated_changes:
                            assert change.before is not None
                            current = current_by_name[change.context_name]
                            expected_digest = context_record_digest(current)
                            restored = self._context_for_restoration(
                                change.before,
                                context_uid=change.context_uid,
                                context_name=change.context_name,
                                expected_context_digest=expected_digest,
                            )
                            checkpoint = self._save_locked(
                                restored,
                                AutoCheckpoint(
                                    command="undo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        f"Undo command 'mem merge' [{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=expected_digest,
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Merge restoration created no Undo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            updated_written.append((change.context_name, checkpoint))

                        for change in created_changes:
                            current = current_by_name[change.context_name]
                            checkpoint = self._save_locked(
                                current,
                                AutoCheckpoint(
                                    command="undo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        f"Undo command 'mem merge' [{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(current),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Merge restoration created no Undo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            created_saved.append((change.context_name, checkpoint))
                            archive = self._command_context_archive_path(
                                change.checkpoint_uid
                            )
                            root = archive.parent
                            root.mkdir(parents=True, exist_ok=True, mode=0o700)
                            if root.is_symlink() or not root.is_dir():
                                raise ValueError(
                                    "Command Context archive storage is invalid."
                                )
                            if archive.exists() or archive.is_symlink():
                                raise ConcurrentContextUpdateError(
                                    "A Merge command archive already exists."
                                )
                            archive.mkdir(mode=0o700)
                            context_file = self._context_file(change.context_name)
                            checkpoints_dir = self._checkpoints_dir(change.context_name)
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
                                    "command": "merge",
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
                                archived_checkpoints.rename(
                                    self._checkpoints_dir(change.context_name)
                                )
                                archived_context.rename(
                                    self._context_file(change.context_name)
                                )
                                checkpoint = next(
                                    checkpoint
                                    for name, checkpoint in created_saved
                                    if name == change.context_name
                                )
                                self._remove_checkpoint_uid_locked(
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
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name, checkpoint in reversed(updated_written):
                            try:
                                _write_bytes_atomic(
                                    self._context_file(name),
                                    original_bytes[name],
                                )
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Merge Undo failed and its Context tree could not "
                                "be fully rolled back."
                            ) from rollback_error
                        raise
                else:
                    current_by_name: dict[str, Context] = {}
                    original_bytes: dict[str, bytes] = {}
                    archives: dict[str, tuple[object, object, Context]] = {}
                    for change in updated_changes:
                        assert change.before is not None
                        try:
                            current = self.load_direct(change.context_name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' "
                                "no longer exists."
                            ) from error
                        if current.uid != change.context_uid or context_record_digest(
                            current
                        ) != context_record_digest(change.before):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' changed "
                                "after the Merge selected for redo."
                            )
                        current_by_name[change.context_name] = current
                        original_bytes[change.context_name] = self._context_file(
                            change.context_name
                        ).read_bytes()
                    for change in created_changes:
                        if self.context_exists(change.context_name):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' already exists."
                            )
                        archive, manifest, archived, _entries = (
                            self._load_command_context_archive(change.checkpoint_uid)
                        )
                        assert change.after is not None
                        if (
                            manifest.get("command") != "merge"
                            or manifest.get("unit_uid") != unit.uid
                            or archived.uid != change.context_uid
                            or archived.name != change.context_name
                            or context_record_digest(archived)
                            != context_record_digest(change.after)
                        ):
                            raise ConcurrentContextUpdateError(
                                "The archived Merge result changed before Redo."
                            )
                        archives[change.context_name] = (
                            archive,
                            manifest,
                            archived,
                        )

                    updated_written: list[tuple[str, Checkpoint]] = []
                    activated: list[tuple[object, object, object, object]] = []
                    moved: list[tuple[object, object, object, object, Checkpoint]] = []
                    try:
                        for change in updated_changes:
                            assert change.after is not None
                            current = current_by_name[change.context_name]
                            expected_digest = context_record_digest(current)
                            restored = self._context_for_restoration(
                                change.after,
                                context_uid=change.context_uid,
                                context_name=change.context_name,
                                expected_context_digest=expected_digest,
                            )
                            checkpoint = self._save_locked(
                                restored,
                                AutoCheckpoint(
                                    command="redo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        f"Redo command 'mem merge' [{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=expected_digest,
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Merge restoration created no Redo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            updated_written.append((change.context_name, checkpoint))

                        for change in created_changes:
                            archive, _manifest, archived = archives[change.context_name]
                            self._assert_context_storage_available(change.context_name)
                            self._context_dir(change.context_name).mkdir(
                                parents=True,
                                exist_ok=True,
                            )
                            context_file = self._context_file(change.context_name)
                            checkpoints_dir = self._checkpoints_dir(change.context_name)
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
                            checkpoint = self._save_locked(
                                archived,
                                AutoCheckpoint(
                                    command="redo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        f"Redo command 'mem merge' [{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(archived),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Merge restoration created no Redo checkpoint."
                                )
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
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                                self._checkpoints_dir(change.context_name).rename(
                                    archived_checkpoints
                                )
                                self._context_file(change.context_name).rename(
                                    archived_context
                                )
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
                                self._checkpoints_dir(change.context_name).rename(
                                    archived_checkpoints
                                )
                                self._context_file(change.context_name).rename(
                                    archived_context
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name, checkpoint in reversed(updated_written):
                            try:
                                _write_bytes_atomic(
                                    self._context_file(name),
                                    original_bytes[name],
                                )
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Merge Redo failed and its Context tree could not "
                                "be fully rolled back."
                            ) from rollback_error
                        raise
                    for change, archive, *_rest in moved:
                        manifest = archive / "manifest.json"
                        manifest.unlink()
                        archive.rmdir()
                    try:
                        self.command_context_archives_dir.rmdir()
                    except OSError:
                        pass

        return CommandRestoreResult(
            unit=unit,
            direction=direction,
            receipt_uid=receipt_uid,
            checkpoints=tuple(checkpoints),
        )
