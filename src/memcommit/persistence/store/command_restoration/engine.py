"""Coordinate command Undo/Redo, companion sessions, and rollback."""

from __future__ import annotations
import json
import uuid
from pathlib import Path
from memcommit.core.context import AutoCheckpoint, Checkpoint
from ..context_memory.models import ConcurrentContextUpdateError
from ..context_memory.records import (
    context_record_digest,
)
from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)


class _CommandRestorationEngineMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    def restore_recent_context_command(
        self,
        direction: str,
        *,
        expected_unit_uid: str | None = None,
    ):
        """Undo or redo one globally ordered checkpoint-producing command.

        The command stack is reconstructed while the store-wide command lock
        is held, then every affected Context is freshness-checked and restored
        under one deterministic multi-lock boundary. This supplies exception
        atomicity for multi-Context Update commands; as elsewhere in this
        prototype, a machine crash can still interrupt several file replaces.
        """
        from memcommit.application.retained_history.command_history import (
            CommandHistoryError,
            CommandRestoreResult,
            build_command_stacks,
            command_restore_metadata,
        )

        if direction not in {"undo", "redo"}:
            raise ValueError("Command restoration direction must be undo or redo.")
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            stacks = build_command_stacks(self)
            candidates = stacks.undo if direction == "undo" else stacks.redo
            if not candidates:
                raise CommandHistoryError(
                    f"There is no recorded Context command to {direction}."
                )
            unit = candidates[-1]
            if expected_unit_uid is not None and unit.uid != expected_unit_uid:
                # Granted recovery names one exact authority command from the
                # participant-side receipt. Never substitute a newer, unrelated
                # authority mutation merely because it is currently on top.
                raise CommandHistoryError(
                    "The recorded granted update is not the next Context "
                    f"command to {direction}."
                )
            if any(
                change.before is None or change.after is None for change in unit.changes
            ):
                return self._restore_context_creation_command_locked(
                    unit,
                    direction,
                )
            names = tuple(change.context_name for change in unit.changes)
            receipt_uid = str(uuid.uuid4())
            restore_metadata = command_restore_metadata(
                receipt_uid=receipt_uid,
                direction=direction,
                unit=unit,
            )
            original_records: dict[str, dict[str, object]] = {}
            created_checkpoints: list[tuple[str, Checkpoint]] = []
            written_names: list[str] = []
            companion_session_restore: (
                tuple[Path, dict[str, object], dict[str, object]] | None
            ) = None
            companion_session_written = False
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks(names):
                    for change in unit.changes:
                        try:
                            current = self.load_direct(change.context_name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' "
                                "no longer exists."
                            ) from error
                        expected = (
                            change.after if direction == "undo" else change.before
                        )
                        if current.uid != change.context_uid or context_record_digest(
                            current
                        ) != context_record_digest(expected):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' changed "
                                f"after the command selected for {direction}."
                            )
                        original_records[change.context_name] = current.to_dict()

                    companion_session_restore = self._prepare_companion_session_restore(
                        unit,
                        direction,
                    )

                    try:
                        for change in unit.changes:
                            target_record = (
                                change.before if direction == "undo" else change.after
                            )
                            expected_digest = context_record_digest(
                                original_records[change.context_name]
                            )
                            restored = self._context_for_restoration(
                                target_record,
                                context_uid=change.context_uid,
                                context_name=change.context_name,
                                expected_context_digest=expected_digest,
                            )
                            checkpoint = self._save_locked(
                                restored,
                                AutoCheckpoint(
                                    command=direction,
                                    args={
                                        "command_restore": restore_metadata,
                                    },
                                    description=(
                                        f"{direction.title()} command "
                                        f"'mem {unit.command}' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=expected_digest,
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Command restoration created no checkpoint."
                                )
                            written_names.append(change.context_name)
                            created_checkpoints.append(
                                (change.context_name, checkpoint)
                            )
                        if companion_session_restore is not None:
                            session_path, _session_before, session_after = (
                                companion_session_restore
                            )
                            self._write_companion_session_restore(
                                session_path,
                                expected=_session_before,
                                value=session_after,
                            )
                            companion_session_written = True
                    except Exception:
                        rollback_error: Exception | None = None
                        if (
                            companion_session_written
                            and companion_session_restore is not None
                        ):
                            try:
                                session_path, session_before, _session_after = (
                                    companion_session_restore
                                )
                                self._write_companion_session_restore(
                                    session_path,
                                    expected=_session_after,
                                    value=session_before,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name in written_names:
                            try:
                                _write_json_atomic(
                                    self._context_file(name),
                                    original_records[name],
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name, checkpoint in created_checkpoints:
                            try:
                                removed = False
                                for path in self._checkpoints_dir(name).glob(
                                    f"*-{checkpoint.uid[:8]}.json"
                                ):
                                    if path.is_symlink() or not path.is_file():
                                        continue
                                    with open(path, encoding="utf-8") as file:
                                        value = json.load(
                                            file,
                                            object_pairs_hook=(
                                                _reject_duplicate_json_keys
                                            ),
                                        )
                                    if value.get("uid") == checkpoint.uid:
                                        path.unlink()
                                        removed = True
                                        break
                                if not removed:
                                    raise RuntimeError(
                                        "Restoration checkpoint could not be "
                                        "found during rollback."
                                    )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Command restoration failed and its Contexts "
                                "could not be fully rolled back."
                            ) from rollback_error
                        raise
            return CommandRestoreResult(
                unit=unit,
                direction=direction,
                receipt_uid=receipt_uid,
                checkpoints=tuple(checkpoint for _, checkpoint in created_checkpoints),
            )

    def _restore_context_creation_command_locked(self, unit, direction: str):
        """Restore one command unit that includes created Context lifecycles."""

        if unit.command == "branch":
            return self._restore_branch_context_creation_command_locked(
                unit,
                direction,
            )
        if unit.command == "merge":
            return self._restore_merge_context_creation_command_locked(
                unit,
                direction,
            )
        if unit.command == "sever":
            return self._restore_sever_context_creation_command_locked(
                unit,
                direction,
            )
        if unit.command == "atomize":
            return self._restore_atomize_context_creation_command_locked(
                unit,
                direction,
            )
        raise ValueError(
            f"Command '{unit.command}' has no Context-creation restoration."
        )

    def _prepare_companion_session_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare a saved operation session coupled to one Context command."""
        if unit.command == "meld":
            return self._prepare_meld_command_restore(unit, direction)
        if unit.command == "sever":
            return self._prepare_sever_command_restore(unit, direction)
        if unit.command == "atomize-grounding":
            return self._prepare_atomize_grounding_command_restore(unit, direction)
        if unit.command == "update":
            return self._prepare_update_command_restore(unit, direction)
        return None

    def _write_companion_session_restore(
        self,
        path: Path,
        *,
        expected: dict[str, object],
        value: dict[str, object],
    ) -> None:
        """CAS-write one companion session inside command restoration."""
        if path == self.staged_update_file:
            with self._update_session_write_lock():
                current = self._load_update_session(path)
                if current is None or current.to_dict() != expected:
                    raise ConcurrentContextUpdateError(
                        "The active Update receipt changed during restoration."
                    )
                from memcommit.application.operations.update.model import UpdateSession

                self._save_update_session(path, UpdateSession.from_dict(value))
            return
        from memcommit.application.operations.sever.session_store import (
            SeverSessionStore,
        )

        sever_sessions = SeverSessionStore(self)
        if path.parent == sever_sessions.directory:
            uid = path.stem
            if path != sever_sessions._path(uid):
                raise ConcurrentContextUpdateError(
                    "The Sever session restore path is invalid."
                )
            with self.profile_write_guard():
                with sever_sessions._write_lock(uid):
                    if not path.is_file() or path.is_symlink():
                        raise ConcurrentContextUpdateError(
                            "The applied Sever session changed during restoration."
                        )
                    with open(path, encoding="utf-8") as file:
                        current = json.load(
                            file,
                            object_pairs_hook=_reject_duplicate_json_keys,
                        )
                    if current != expected:
                        raise ConcurrentContextUpdateError(
                            "The applied Sever session changed during restoration."
                        )
                    _write_json_atomic(path, value)
            return
        with self.profile_write_guard():
            if not path.is_file() or path.is_symlink():
                raise ConcurrentContextUpdateError(
                    "The companion operation session changed during restoration."
                )
            with open(path, encoding="utf-8") as file:
                current = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if current != expected:
                raise ConcurrentContextUpdateError(
                    "The companion operation session changed during restoration."
                )
            _write_json_atomic(path, value)
