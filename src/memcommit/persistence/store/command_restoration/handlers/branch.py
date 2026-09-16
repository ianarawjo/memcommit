"""Restore exact Branch-created Context trees."""

from __future__ import annotations
import uuid
from pathlib import Path
from typing import Any, Literal
from memcommit.core.context import AutoCheckpoint, Checkpoint, Context
from memcommit.core.context_navigation import (
    record_current_context_transition,
)
from ...context_memory.models import ConcurrentContextUpdateError
from ...context_memory.records import (
    context_record_digest,
)
from ...infrastructure.atomic_io import (
    _write_json_atomic,
)


class _BranchRestorationMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    def _restore_branch_context_creation_command_locked(
        self,
        unit,
        direction: Literal["undo", "redo"],
    ):
        """Undo or redo one exact Branch or complete lexical subtree.

        Undo moves the created Context records and their inherited histories
        into private command archives. Redo restores those exact identities;
        it must not synthesize a fresh Branch from a Source that may have
        changed since the original command.
        """

        from memcommit.application.capabilities.command_recovery import (
            CommandHistoryError,
            CommandRestoreResult,
            branch_tree_receipt,
            command_restore_metadata,
        )

        if (
            unit.command != "branch"
            or not unit.changes
            or any(
                change.before is not None or change.after is None
                for change in unit.changes
            )
            or not unit.checkpoint_args
        ):
            raise ValueError(
                "Branch lifecycle restoration requires one complete creation unit."
            )
        try:
            receipts = tuple(branch_tree_receipt(args) for args in unit.checkpoint_args)
        except CommandHistoryError as error:
            raise ValueError(str(error)) from error
        receipt = receipts[0]
        if (
            any(candidate != receipt for candidate in receipts[1:])
            or unit.uid != f"branch:{receipt.operation_uid}"
            or {(change.context_uid, change.context_name) for change in unit.changes}
            != {(item.target_uid, item.target_name) for item in receipt.contexts}
        ):
            raise ValueError("Branch lifecycle receipts are inconsistent.")

        names = tuple(change.context_name for change in unit.changes)
        name_set = set(names)
        receipt_uid = str(uuid.uuid4())
        restore_metadata = command_restore_metadata(
            receipt_uid=receipt_uid,
            direction=direction,
            unit=unit,
        )
        checkpoints: list[Checkpoint] = []

        def move_record_and_history(
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

        with self._context_graph_lock(exclusive=True):
            with self._context_write_locks(names):
                if direction == "undo":
                    current_by_name: dict[str, Context] = {}
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
                                "after the Branch selected for undo."
                            )
                        self._assert_context_deletion_allowed(current)
                        current_by_name[change.context_name] = current

                    archives = {
                        change.context_name: self._command_context_archive_path(
                            change.checkpoint_uid
                        )
                        for change in unit.changes
                    }
                    root = self.command_context_archives_dir
                    if any(
                        archive.exists() or archive.is_symlink()
                        for archive in archives.values()
                    ):
                        raise ConcurrentContextUpdateError(
                            "A Branch command archive already exists."
                        )

                    saved: list[tuple[str, Checkpoint]] = []
                    moved: list[tuple[Any, Path, Path, Path]] = []
                    created_archives: list[Path] = []
                    undo_original_state: dict[str, object] | None = None
                    state_changed = False
                    try:
                        root.mkdir(parents=True, exist_ok=True, mode=0o700)
                        if root.is_symlink() or not root.is_dir():
                            raise ValueError(
                                "Command Context archive storage is invalid."
                            )
                        for change in unit.changes:
                            current = current_by_name[change.context_name]
                            checkpoint = self._save_locked(
                                current,
                                AutoCheckpoint(
                                    command="undo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        f"Undo command 'mem branch' [{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(current),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Branch restoration created no Undo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            saved.append((change.context_name, checkpoint))
                            archive = archives[change.context_name]
                            archive.mkdir(mode=0o700)
                            created_archives.append(archive)
                            context_file = self._context_file(change.context_name)
                            checkpoints_dir = self._checkpoints_dir(change.context_name)
                            archived_context = archive / "context.json"
                            archived_checkpoints = archive / "checkpoints"
                            move_record_and_history(
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
                        with self._state_write_lock():
                            state = self._read_state()
                            undo_original_state = dict(state)
                            if state.get("current") in name_set:
                                record_current_context_transition(
                                    state,
                                    receipt.current_before,
                                )
                                self._write_state(state)
                                state_changed = True
                    except Exception:
                        undo_rollback_error: Exception | None = None
                        if state_changed and undo_original_state is not None:
                            try:
                                with self._state_write_lock():
                                    self._write_state(undo_original_state)
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
                                move_record_and_history(
                                    archived_context,
                                    archived_checkpoints,
                                    self._context_file(change.context_name),
                                    self._checkpoints_dir(change.context_name),
                                )
                                checkpoint = next(
                                    candidate
                                    for name, candidate in saved
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
                                self._remove_checkpoint_uid_locked(
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
                else:
                    archived: dict[
                        str,
                        tuple[Path, dict[str, object], Context],
                    ] = {}
                    for change in unit.changes:
                        if self.context_exists(change.context_name):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' already "
                                "exists."
                            )
                        archive_path, archive_manifest, archived_record, _entries = (
                            self._load_command_context_archive(change.checkpoint_uid)
                        )
                        assert change.after is not None
                        if (
                            archive_manifest.get("command") != "branch"
                            or archive_manifest.get("unit_uid") != unit.uid
                            or archived_record.uid != change.context_uid
                            or archived_record.name != change.context_name
                            or context_record_digest(archived_record)
                            != context_record_digest(change.after)
                        ):
                            raise ConcurrentContextUpdateError(
                                "The archived Branch result changed before Redo."
                            )
                        self._assert_context_storage_available(change.context_name)
                        archived[change.context_name] = (
                            archive_path,
                            archive_manifest,
                            archived_record,
                        )

                    activated: list[tuple[Any, Path, Path, Path]] = []
                    redone: list[tuple[Any, Path, Path, Path, Checkpoint]] = []
                    redo_original_state: dict[str, object] | None = None
                    state_changed = False
                    try:
                        for change in unit.changes:
                            archive, _manifest, context = archived[change.context_name]
                            self._context_dir(change.context_name).mkdir(
                                parents=True,
                                exist_ok=True,
                            )
                            context_file = self._context_file(change.context_name)
                            checkpoints_dir = self._checkpoints_dir(change.context_name)
                            archived_context = archive / "context.json"
                            archived_checkpoints = archive / "checkpoints"
                            move_record_and_history(
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
                            checkpoint = self._save_locked(
                                context,
                                AutoCheckpoint(
                                    command="redo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        f"Redo command 'mem branch' [{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(context),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Branch restoration created no Redo checkpoint."
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
                        with self._state_write_lock():
                            state = self._read_state()
                            redo_original_state = dict(state)
                            if state.get("current") == receipt.current_before:
                                record_current_context_transition(
                                    state,
                                    receipt.target_root,
                                )
                                self._write_state(state)
                                state_changed = True
                    except Exception:
                        redo_rollback_error: Exception | None = None
                        if state_changed and redo_original_state is not None:
                            try:
                                with self._state_write_lock():
                                    self._write_state(redo_original_state)
                            except Exception as candidate:
                                redo_rollback_error = redo_rollback_error or candidate
                        redone_names = {
                            change.context_name for change, *_rest in redone
                        }
                        for (
                            change,
                            _archive,
                            archived_context,
                            archived_checkpoints,
                            checkpoint,
                        ) in reversed(redone):
                            try:
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                                move_record_and_history(
                                    self._context_file(change.context_name),
                                    self._checkpoints_dir(change.context_name),
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
                                move_record_and_history(
                                    self._context_file(change.context_name),
                                    self._checkpoints_dir(change.context_name),
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
                        self.command_context_archives_dir.rmdir()
                    except OSError:
                        pass

        return CommandRestoreResult(
            unit=unit,
            direction=direction,
            receipt_uid=receipt_uid,
            checkpoints=tuple(checkpoints),
        )
