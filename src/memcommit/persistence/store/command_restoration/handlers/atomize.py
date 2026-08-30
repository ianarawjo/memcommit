"""Restore exact Atomize-created Contexts."""

from __future__ import annotations
import copy
from contextlib import ExitStack
import json
import uuid
from typing import Iterable
from memcommit.core.context import AutoCheckpoint, Checkpoint
from memcommit.core.context_navigation import (
    record_current_context_transition,
)
from ...context_memory.models import ConcurrentContextUpdateError
from ...context_memory.records import (
    context_record_digest,
)
from ...infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)


class _AtomizeRestorationMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    def _restore_atomize_context_creation_command_locked(self, unit, direction: str):
        """Undo/Redo one final Atomize Save As output and its Source receipt."""

        from memcommit.application.operations.atomize.domain import (
            AtomizeAnalysisSession,
        )
        from memcommit.application.operations.atomize.records import (
            atomize_review_record_digest,
        )
        from memcommit.application.capabilities.retained_history.command_history import (
            CommandRestoreResult,
            command_restore_metadata,
        )

        if (
            unit.command != "atomize"
            or len(unit.changes) != 1
            or unit.changes[0].before is not None
            or unit.changes[0].after is None
        ):
            raise ValueError(
                "Only an exact Atomize Save As creation can use lifecycle restoration."
            )
        change = unit.changes[0]
        receipt_uid = str(uuid.uuid4())
        restore_metadata = command_restore_metadata(
            receipt_uid=receipt_uid,
            direction=direction,
            unit=unit,
        )
        checkpoint: Checkpoint | None = None

        def load_creation_receipt(
            entries: Iterable[dict[str, object]],
        ) -> tuple[dict[str, object], dict[str, object]]:
            source_checkpoint = next(
                (
                    entry
                    for entry in entries
                    if entry.get("uid") == change.checkpoint_uid
                ),
                None,
            )
            args = (
                source_checkpoint.get("args")
                if isinstance(source_checkpoint, dict)
                else None
            )
            creation = args.get("context_creation") if isinstance(args, dict) else None
            save_as = args.get("atomize_save_as") if isinstance(args, dict) else None
            if (
                creation
                != {
                    "version": 1,
                    "context_uid": change.context_uid,
                    "context_name": change.context_name,
                }
                or not isinstance(save_as, dict)
                or set(save_as)
                != {
                    "version",
                    "source_context",
                    "source_frame",
                    "source_frame_digest",
                    "source_analysis_uid",
                    "source_workbench",
                    "current_before",
                }
                or save_as.get("version") != 1
            ):
                raise ValueError(
                    "Atomize checkpoint has no valid Save As creation receipt."
                )
            return args, save_as

        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(change.context_name):
                if direction == "undo":
                    try:
                        current = self.load_direct(change.context_name)
                    except FileNotFoundError as error:
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' no "
                            "longer exists."
                        ) from error
                    if current.uid != change.context_uid or context_record_digest(
                        current
                    ) != context_record_digest(change.after):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' changed "
                            "after the Atomize Save As selected for undo."
                        )
                    self._assert_context_deletion_allowed(current)
                    entries = self.list_checkpoints(change.context_name)
                    args, save_as = load_creation_receipt(entries)
                    source_record = save_as.get("source_context")
                    if not isinstance(source_record, dict) or set(source_record) != {
                        "uid",
                        "name",
                        "digest",
                    }:
                        raise ValueError("Atomize Save As Source receipt is invalid.")
                    source_uid = source_record.get("uid")
                    source_name = source_record.get("name")
                    analysis_uid = save_as.get("source_analysis_uid")
                    current_before = save_as.get("current_before")
                    if (
                        not isinstance(source_uid, str)
                        or not isinstance(source_name, str)
                        or not isinstance(analysis_uid, str)
                        or (
                            current_before is not None
                            and not isinstance(current_before, str)
                        )
                    ):
                        raise ValueError("Atomize Save As Source receipt is invalid.")
                    with ExitStack() as session_locks:
                        for context_uid in sorted({source_uid, change.context_uid}):
                            session_locks.enter_context(
                                self._atomize_session_write_lock(context_uid)
                            )
                        source_analysis = self.load_atomize_analysis(source_uid)
                        output_analysis = self.load_atomize_analysis(change.context_uid)
                        if (
                            source_analysis is None
                            or output_analysis is None
                            or source_analysis.uid != analysis_uid
                            or output_analysis.uid != analysis_uid
                            or output_analysis.context_uid != change.context_uid
                            or output_analysis.context_name != change.context_name
                            or args.get("analysis_uid") != analysis_uid
                        ):
                            raise ValueError(
                                "Atomize analyses do not match the restored "
                                "Save As command."
                            )
                        source_workbench_record = save_as.get("source_workbench")
                        terminal = self.load_atomize_workbench(source_analysis)
                        reviewing = None
                        reviewing_digest = None
                        terminal_digest = None
                        if source_workbench_record is None:
                            if terminal is not None:
                                raise ConcurrentContextUpdateError(
                                    "The Source Atomize workbench changed before Undo."
                                )
                        else:
                            if (
                                not isinstance(source_workbench_record, dict)
                                or set(source_workbench_record)
                                != {"uid", "output_context_name", "record_digest"}
                                or terminal is None
                                or terminal.uid != source_workbench_record.get("uid")
                            ):
                                raise ValueError(
                                    "Atomize Source workbench receipt is invalid."
                                )
                            terminal_digest = atomize_review_record_digest(terminal)
                            reviewing = copy.deepcopy(terminal)
                            reviewing.clear_application(
                                output_context_name=change.context_name,
                                checkpoint_uid=change.checkpoint_uid,
                                restore_output_context_name=(
                                    source_workbench_record.get("output_context_name")
                                ),
                            )
                            reviewing_digest = atomize_review_record_digest(reviewing)
                            if reviewing_digest != source_workbench_record.get(
                                "record_digest"
                            ):
                                raise ConcurrentContextUpdateError(
                                    "The Source Atomize workbench changed before Undo."
                                )

                        checkpoint = self._save_locked(
                            current,
                            AutoCheckpoint(
                                command="undo",
                                args={"command_restore": restore_metadata},
                                description=(
                                    f"Undo command 'mem atomize' [{receipt_uid[:8]}]"
                                ),
                            ),
                            expected_context_digest=context_record_digest(current),
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Atomize restoration created no Undo checkpoint."
                            )
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
                                "An Atomize command archive already exists."
                            )
                        archive.mkdir(mode=0o700)
                        context_file = self._context_file(change.context_name)
                        checkpoints_dir = self._checkpoints_dir(change.context_name)
                        analysis_path = self._atomize_analysis_path(change.context_uid)
                        archived_context = archive / "context.json"
                        archived_checkpoints = archive / "checkpoints"
                        archived_analysis = archive / "atomize-analysis.json"
                        moved = False
                        workbench_saved = False
                        original_state: dict[str, object] | None = None
                        state_changed = False
                        try:
                            context_file.rename(archived_context)
                            checkpoints_dir.rename(archived_checkpoints)
                            analysis_path.rename(archived_analysis)
                            moved = True
                            _write_json_atomic(
                                archive / "manifest.json",
                                {
                                    "version": 1,
                                    "command": "atomize",
                                    "unit_uid": unit.uid,
                                    "context_uid": change.context_uid,
                                    "context_name": change.context_name,
                                    "checkpoint_uid": change.checkpoint_uid,
                                    "analysis_uid": analysis_uid,
                                    "source_context_uid": source_uid,
                                    "source_context_name": source_name,
                                    "source_workbench": source_workbench_record,
                                    "reviewing_workbench_digest": reviewing_digest,
                                    "terminal_workbench_digest": terminal_digest,
                                    "current_before": current_before,
                                },
                            )
                            if reviewing is not None:
                                self._save_atomize_workbench_locked(reviewing)
                                workbench_saved = True
                            with self._state_write_lock():
                                state = self._read_state()
                                original_state = dict(state)
                                if state.get("current") == change.context_name:
                                    record_current_context_transition(
                                        state,
                                        current_before,
                                    )
                                    self._write_state(state)
                                    state_changed = True
                        except Exception:
                            if state_changed and original_state is not None:
                                with self._state_write_lock():
                                    self._write_state(original_state)
                            if workbench_saved and terminal is not None:
                                self._save_atomize_workbench_locked(terminal)
                            if moved:
                                archived_analysis.rename(analysis_path)
                                archived_checkpoints.rename(checkpoints_dir)
                                archived_context.rename(context_file)
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                            manifest_path = archive / "manifest.json"
                            if (
                                manifest_path.exists()
                                and not manifest_path.is_symlink()
                            ):
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
                    archive, manifest, archived_context, entries = (
                        self._load_command_context_archive(change.checkpoint_uid)
                    )
                    _args, save_as = load_creation_receipt(entries)
                    if (
                        manifest.get("command") != "atomize"
                        or manifest.get("unit_uid") != unit.uid
                        or archived_context.uid != change.context_uid
                        or archived_context.name != change.context_name
                        or context_record_digest(archived_context)
                        != context_record_digest(change.after)
                    ):
                        raise ConcurrentContextUpdateError(
                            "The archived Atomize result changed before Redo."
                        )
                    source_uid = manifest.get("source_context_uid")
                    analysis_uid = manifest.get("analysis_uid")
                    assert isinstance(source_uid, str)
                    assert isinstance(analysis_uid, str)
                    with ExitStack() as session_locks:
                        for context_uid in sorted({source_uid, change.context_uid}):
                            session_locks.enter_context(
                                self._atomize_session_write_lock(context_uid)
                            )
                        source_analysis = self.load_atomize_analysis(source_uid)
                        if (
                            source_analysis is None
                            or source_analysis.uid != analysis_uid
                        ):
                            raise ConcurrentContextUpdateError(
                                "The Source Atomize analysis changed before Redo."
                            )
                        source_workbench_record = manifest.get("source_workbench")
                        reviewing = self.load_atomize_workbench(source_analysis)
                        terminal = None
                        if source_workbench_record is None:
                            if reviewing is not None:
                                raise ConcurrentContextUpdateError(
                                    "The Source Atomize workbench changed before Redo."
                                )
                        else:
                            if reviewing is None or atomize_review_record_digest(
                                reviewing
                            ) != manifest.get("reviewing_workbench_digest"):
                                raise ConcurrentContextUpdateError(
                                    "The Source Atomize workbench changed before Redo."
                                )
                            terminal = copy.deepcopy(reviewing)
                            terminal.output_context_name = change.context_name
                            terminal.record_application(
                                output_context_name=change.context_name,
                                checkpoint_uid=change.checkpoint_uid,
                            )
                            if atomize_review_record_digest(terminal) != manifest.get(
                                "terminal_workbench_digest"
                            ):
                                raise ConcurrentContextUpdateError(
                                    "The terminal Atomize workbench changed "
                                    "before Redo."
                                )
                        archived_analysis = archive / "atomize-analysis.json"
                        if (
                            archived_analysis.is_symlink()
                            or not archived_analysis.is_file()
                        ):
                            raise ValueError("Archived Atomize analysis is invalid.")
                        with open(archived_analysis, encoding="utf-8") as file:
                            output_analysis = AtomizeAnalysisSession.from_dict(
                                json.load(
                                    file,
                                    object_pairs_hook=_reject_duplicate_json_keys,
                                )
                            )
                        if (
                            output_analysis.uid != analysis_uid
                            or output_analysis.context_uid != change.context_uid
                            or output_analysis.context_name != change.context_name
                        ):
                            raise ValueError(
                                "Archived Atomize analysis identity is invalid."
                            )
                        self._assert_context_storage_available(change.context_name)
                        context_dir = self._context_dir(change.context_name)
                        context_dir.mkdir(parents=True, exist_ok=True)
                        context_file = self._context_file(change.context_name)
                        checkpoints_dir = self._checkpoints_dir(change.context_name)
                        analysis_path = self._atomize_analysis_path(change.context_uid)
                        archived_context_file = archive / "context.json"
                        archived_checkpoints = archive / "checkpoints"
                        moved = False
                        workbench_saved = False
                        original_state: dict[str, object] | None = None
                        state_changed = False
                        try:
                            archived_context_file.rename(context_file)
                            archived_checkpoints.rename(checkpoints_dir)
                            archived_analysis.rename(analysis_path)
                            moved = True
                            checkpoint = self._save_locked(
                                archived_context,
                                AutoCheckpoint(
                                    command="redo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        "Redo command 'mem atomize' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(
                                    archived_context
                                ),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Atomize restoration created no Redo checkpoint."
                                )
                            if terminal is not None:
                                self._save_atomize_workbench_locked(terminal)
                                workbench_saved = True
                            with self._state_write_lock():
                                state = self._read_state()
                                original_state = dict(state)
                                if state.get("current") == manifest.get(
                                    "current_before"
                                ):
                                    record_current_context_transition(
                                        state,
                                        change.context_name,
                                    )
                                    self._write_state(state)
                                    state_changed = True
                        except Exception:
                            if state_changed and original_state is not None:
                                with self._state_write_lock():
                                    self._write_state(original_state)
                            if workbench_saved and reviewing is not None:
                                self._save_atomize_workbench_locked(reviewing)
                            if moved:
                                if checkpoint is not None:
                                    self._remove_checkpoint_uid_locked(
                                        change.context_name,
                                        checkpoint.uid,
                                    )
                                analysis_path.rename(archived_analysis)
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
