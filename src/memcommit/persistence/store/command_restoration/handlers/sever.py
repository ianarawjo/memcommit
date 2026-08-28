"""Restore exact Sever-created Contexts."""

from __future__ import annotations
import uuid
from memcommit.core.context import AutoCheckpoint, Checkpoint
from memcommit.core.context_targeting.navigation import (
    record_current_context_transition,
)
from ...context_memory.models import ConcurrentContextUpdateError
from ...context_memory.records import (
    context_record_digest,
)
from ...infrastructure.atomic_io import (
    _write_json_atomic,
)


class _SeverRestorationMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    def _restore_sever_context_creation_command_locked(self, unit, direction: str):
        """Undo/Redo one Sever output creation and its saved review.

        Undo moves the complete Context record and checkpoint directory into a
        private command archive instead of destroying them. Redo can therefore
        restore the same identity and history, including every restoration
        receipt, without copying Memory text into lifecycle metadata.
        """
        from memcommit.application.retained_history.command_history import (
            CommandRestoreResult,
            command_restore_metadata,
        )
        from memcommit.application.operations.sever.model import (
            SeverApplication,
            sever_record_digest,
        )
        from memcommit.application.operations.sever.session_store import (
            SeverSessionStore,
        )

        if (
            unit.command != "sever"
            or len(unit.changes) != 1
            or unit.changes[0].before is not None
            or unit.changes[0].after is None
        ):
            raise ValueError(
                "Only an exact Sever Context creation can use lifecycle restoration."
            )
        change = unit.changes[0]
        receipt_uid = str(uuid.uuid4())
        restore_metadata = command_restore_metadata(
            receipt_uid=receipt_uid,
            direction=direction,
            unit=unit,
        )
        sessions = SeverSessionStore(self)
        checkpoint: Checkpoint | None = None

        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(change.context_name):
                if direction == "undo":
                    try:
                        current = self.load_direct(change.context_name)
                    except FileNotFoundError as error:
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' no longer exists."
                        ) from error
                    if current.uid != change.context_uid or context_record_digest(
                        current
                    ) != context_record_digest(change.after):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' changed "
                            "after the command selected for undo."
                        )
                    self._assert_context_deletion_allowed(current)
                    source_checkpoint = next(
                        (
                            entry
                            for entry in self.list_checkpoints(change.context_name)
                            if entry.get("uid") == change.checkpoint_uid
                        ),
                        None,
                    )
                    args = (
                        source_checkpoint.get("args")
                        if isinstance(source_checkpoint, dict)
                        else None
                    )
                    sever_receipt = (
                        args.get("sever") if isinstance(args, dict) else None
                    )
                    session_uid = (
                        sever_receipt.get("session_uid")
                        if isinstance(sever_receipt, dict)
                        else None
                    )
                    if not isinstance(session_uid, str) or not session_uid:
                        raise ValueError(
                            "Sever checkpoint has no valid session receipt."
                        )
                    session = sessions.load(session_uid)
                    application = session.application
                    if (
                        session.state != "APPLIED"
                        or application is None
                        or session.output_name != change.context_name
                        or application.output_context_uid != change.context_uid
                        or application.checkpoint_uid != change.checkpoint_uid
                        or tuple(current.memories) != application.result_memory_uids
                    ):
                        raise ValueError(
                            "Sever session does not match the restored command."
                        )
                    reviewing = session.clear_application(
                        output_context_uid=change.context_uid,
                        checkpoint_uid=change.checkpoint_uid,
                    )
                    session_before_digest = sever_record_digest(session)
                    reviewing_digest = sever_record_digest(reviewing)
                    checkpoint = self._save_locked(
                        current,
                        AutoCheckpoint(
                            command="undo",
                            args={"command_restore": restore_metadata},
                            description=(
                                f"Undo command 'mem sever' [{receipt_uid[:8]}]"
                            ),
                        ),
                        expected_context_digest=context_record_digest(current),
                    )
                    if checkpoint is None:
                        raise RuntimeError(
                            "Sever restoration created no Undo checkpoint."
                        )
                    archive = self._command_context_archive_path(change.checkpoint_uid)
                    root = archive.parent
                    root.mkdir(parents=True, exist_ok=True, mode=0o700)
                    if root.is_symlink() or not root.is_dir():
                        raise ValueError("Command Context archive storage is invalid.")
                    if archive.exists() or archive.is_symlink():
                        raise ConcurrentContextUpdateError(
                            "A Sever command archive already exists."
                        )
                    archive.mkdir(mode=0o700)
                    context_file = self._context_file(change.context_name)
                    checkpoints_dir = self._checkpoints_dir(change.context_name)
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
                            {
                                "version": 1,
                                "command": "sever",
                                "unit_uid": unit.uid,
                                "context_uid": change.context_uid,
                                "context_name": change.context_name,
                                "checkpoint_uid": change.checkpoint_uid,
                                "session_uid": session.uid,
                                "application": application.to_dict(),
                                "reviewing_session_digest": reviewing_digest,
                            },
                        )
                        sessions.save(
                            reviewing,
                            expected_digest=session_before_digest,
                        )
                        session_saved = True
                        with self._state_write_lock():
                            state = self._read_state()
                            if state.get("current") == change.context_name:
                                record_current_context_transition(state, None)
                                self._write_state(state)
                    except Exception:
                        if session_saved:
                            sessions.save(
                                session,
                                expected_digest=reviewing_digest,
                            )
                        if moved:
                            archived_checkpoints.rename(checkpoints_dir)
                            archived_context.rename(context_file)
                            self._remove_checkpoint_uid_locked(
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
                else:
                    if self.context_exists(change.context_name):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' already exists."
                        )
                    archive, manifest, archived_context, _entries = (
                        self._load_command_context_archive(change.checkpoint_uid)
                    )
                    if (
                        archived_context.uid != change.context_uid
                        or archived_context.name != change.context_name
                        or context_record_digest(archived_context)
                        != context_record_digest(change.after)
                    ):
                        raise ConcurrentContextUpdateError(
                            "The archived Sever result changed before Redo."
                        )
                    session_uid = manifest["session_uid"]
                    assert isinstance(session_uid, str)
                    session = sessions.load(session_uid)
                    if (
                        sever_record_digest(session)
                        != manifest["reviewing_session_digest"]
                    ):
                        raise ConcurrentContextUpdateError(
                            "The Sever session changed before Redo."
                        )
                    application = SeverApplication.from_dict(manifest["application"])
                    applied = session.with_application(application)
                    session_before_digest = sever_record_digest(session)
                    self._assert_context_storage_available(change.context_name)
                    context_dir = self._context_dir(change.context_name)
                    context_dir.mkdir(parents=True, exist_ok=True)
                    context_file = self._context_file(change.context_name)
                    checkpoints_dir = self._checkpoints_dir(change.context_name)
                    archived_context_file = archive / "context.json"
                    archived_checkpoints = archive / "checkpoints"
                    moved = False
                    try:
                        archived_context_file.rename(context_file)
                        archived_checkpoints.rename(checkpoints_dir)
                        moved = True
                        checkpoint = self._save_locked(
                            archived_context,
                            AutoCheckpoint(
                                command="redo",
                                args={"command_restore": restore_metadata},
                                description=(
                                    f"Redo command 'mem sever' [{receipt_uid[:8]}]"
                                ),
                            ),
                            expected_context_digest=context_record_digest(
                                archived_context
                            ),
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Sever restoration created no Redo checkpoint."
                            )
                        sessions.save(
                            applied,
                            expected_digest=session_before_digest,
                        )
                    except Exception:
                        if moved:
                            if checkpoint is not None:
                                self._remove_checkpoint_uid_locked(
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
        assert checkpoint is not None
        return CommandRestoreResult(
            unit=unit,
            direction=direction,
            receipt_uid=receipt_uid,
            checkpoints=(checkpoint,),
        )
