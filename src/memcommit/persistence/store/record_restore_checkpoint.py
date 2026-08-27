"""Record Context checkpoints and restore reviewed persistent state."""

from __future__ import annotations

import copy
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import json
import os
import shutil
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Literal, Optional

from memcommit.application.retained_history.checkpoint_frames import map_restorable_checkpoint_frames
from memcommit.core.context import AutoCheckpoint, Checkpoint, Context, Memory, MemoryRef
from memcommit.core.context_targeting.naming import (
    RESERVED_CONTEXT_SEGMENTS,
    validate_portable_context_name,
)
from memcommit.core.context_targeting.navigation import (
    ContextNavigationDirection,
    apply_context_navigation,
    context_navigation_target,
    record_current_context_transition,
    rewrite_context_navigation_names,
)
from memcommit.application.retained_history.context_lifecycle import (
    ContextLifecycleEvent,
    PREVIOUS_CHECKPOINT_NONE,
    PREVIOUS_CHECKPOINT_RECORDED,
    PREVIOUS_CHECKPOINT_UNREADABLE,
)
from memcommit.core.context_targeting.context_catalog import (
    ContextCatalogDiagnostic,
    ContextCatalogDiagnosticCode,
    ContextCatalogScan,
)
from memcommit.application.operations.profile.config import resolve_active_store_dir
from memcommit.application.authority.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)
from memcommit.application.authority.write_protection import (
    WriteProtectionError,
    WriteProtectionRegistry,
    WriteProtectionRegistryError,
    WriteProtectionState,
)
from memcommit.application.retained_history.memory_lineage import (
    MemoryLineageEdge,
    checkpoint_memory_lineage_edges,
    memory_content_sha256,
    memory_lineage_record,
    remap_restoration_snapshot,
)

from .operation_state import (
    ConcurrentContextUpdateError,
    _context_name_parts,
    _reject_duplicate_json_keys,
    _validate_context_header,
    _write_bytes_atomic,
    _write_json_atomic,
    checkpoint_history_digest,
    context_record_digest,
    validate_context_name,
)


class RecordRestoreCheckpointStoreMixin:
    """Temporary Store slice for checkpoint recording and restoration."""

    # --- Checkpoints ---

    # Storage design note:
    # Checkpoints intentionally embed a complete serialization of the Context's
    # direct state.  At the current research-prototype scale, this keeps
    # persistence, recovery, and migration simpler than an object store; nested
    # Contexts and MemoryRefs are already serialized as pointers rather than
    # recursively copied.  If Contexts or histories grow substantially, retain
    # the same logical snapshot semantics while moving Memory contents to
    # content-addressed blobs and having checkpoints point to ordered tree
    # manifests.  A pure delta/event chain is not required by the current model.
    def checkpoint(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
    ) -> Checkpoint:
        """Save a persisted Context snapshot under its cooperative write lock."""
        with self._command_write_lock():
            with self._context_write_lock(ctx.name):
                if not self.context_exists(ctx.name):
                    raise FileNotFoundError(
                        f"Context '{ctx.name}' must be saved before checkpointing."
                    )
                current = self.load_direct(ctx.name)
                expected_digest = getattr(ctx, "_store_digest", None)
                current_digest = context_record_digest(current)
                if current.uid != ctx.uid or (
                    expected_digest is not None and current_digest != expected_digest
                ):
                    # A checkpoint is part of the same serial history as saves and
                    # reverts. Never append a stale caller's snapshot after a
                    # concurrent state change.
                    raise ConcurrentContextUpdateError(
                        f"Context '{ctx.name}' changed before it could be checkpointed."
                    )
                if context_record_digest(ctx) != current_digest:
                    raise ValueError(
                        f"Context '{ctx.name}' has unsaved changes; save it "
                        "before checkpointing."
                    )
                return self._checkpoint_locked(
                    ctx,
                    message=message,
                    command=command,
                    args=args,
                    description=description,
                    auto=auto,
                )

    def checkpoint_context_batch(
        self,
        entries: Iterable[tuple[Context, str]],
        *,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
        expected_context_catalog: Iterable[str] | None = None,
        checkpoint_uids: Iterable[str] | None = None,
    ) -> tuple[Checkpoint, ...]:
        """Append one exception-atomic checkpoint set to existing Contexts.

        Context bytes are unchanged. Every member is locked and revalidated
        before the first history append, and a failed later append removes the
        provisional checkpoints already written by this call. A durable crash
        journal remains outside this prototype boundary.
        """

        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context checkpoint entry is required.")
        if any(
            not isinstance(context, Context)
            or not isinstance(expected_digest, str)
            or not expected_digest
            for context, expected_digest in records
        ):
            raise TypeError("Invalid Context checkpoint batch entry.")
        names = tuple(context.name for context, _expected_digest in records)
        if len(names) != len(set(names)):
            raise ValueError("Context checkpoint batch contains duplicate names.")
        planned_uids = (
            None if checkpoint_uids is None else tuple(checkpoint_uids)
        )
        if planned_uids is not None:
            try:
                canonical_uids = tuple(str(uuid.UUID(value)) for value in planned_uids)
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError("Context checkpoint batch uid plan is invalid.") from error
            if (
                len(planned_uids) != len(records)
                or len(planned_uids) != len(set(planned_uids))
                or planned_uids != canonical_uids
            ):
                raise ValueError("Context checkpoint batch uid plan is invalid.")
        for name in names:
            validate_context_name(name)
        expected_catalog = (
            None
            if expected_context_catalog is None
            else tuple(expected_context_catalog)
        )
        if expected_catalog is not None and (
            len(expected_catalog) != len(set(expected_catalog))
            or any(not isinstance(name, str) or not name for name in expected_catalog)
        ):
            raise ValueError("Expected Context checkpoint catalog is invalid.")

        with self._command_write_lock():
            with self._context_graph_lock(exclusive=expected_catalog is not None):
                if (
                    expected_catalog is not None
                    and tuple(self.list_context_names()) != expected_catalog
                ):
                    raise ConcurrentContextUpdateError(
                        "The Context namespace changed after the checkpoint "
                        "scope was selected."
                    )
                with self._context_write_locks(names):
                    self._assert_profile_write_allowed()
                    for context, expected_digest in records:
                        try:
                            current = self.load_direct(context.name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' no longer exists."
                            ) from error
                        current_digest = context_record_digest(current)
                        if (
                            current.uid != context.uid
                            or current_digest != expected_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' changed before it "
                                "could be checkpointed."
                            )
                        if context_record_digest(context) != current_digest:
                            raise ValueError(
                                f"Context '{context.name}' has unsaved changes; "
                                "save it before checkpointing."
                            )

                    created: list[tuple[str, Checkpoint]] = []
                    try:
                        for index, (context, _expected_digest) in enumerate(records):
                            checkpoint = self._checkpoint_locked(
                                context,
                                message=message,
                                command=command,
                                args=args,
                                description=description,
                                auto=auto,
                                checkpoint_uid=(
                                    None
                                    if planned_uids is None
                                    else planned_uids[index]
                                ),
                            )
                            created.append((context.name, checkpoint))
                    except Exception:
                        rollback_error: Exception | None = None
                        for name, checkpoint in created:
                            try:
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Context checkpoint batch failed and could not "
                                "be fully rolled back."
                            ) from rollback_error
                        raise
        return tuple(checkpoint for _name, checkpoint in created)

    def _checkpoint_locked(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
        command_before: dict[str, object] | None = None,
        checkpoint_uid: str | None = None,
    ) -> Checkpoint:
        """Write one checkpoint while the caller holds the Context lock."""
        self._assert_profile_write_allowed()
        if checkpoint_uid is None:
            checkpoint_uid = str(uuid.uuid4())
        else:
            try:
                canonical_uid = str(uuid.UUID(checkpoint_uid))
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError("Checkpoint uid plan is invalid.") from error
            if checkpoint_uid != canonical_uid:
                raise ValueError("Checkpoint uid plan is invalid.")
        cp = Checkpoint(
            uid=checkpoint_uid,
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
            command=command,
            args=args,
            description=description,
            auto=auto,
        )
        ts = cp.timestamp.strftime("%Y%m%dT%H%M%S")
        slug = (
            message[:24].replace(" ", "-").replace("/", "-")
            if message
            else (command or "checkpoint")
        )
        cp_dir = self._checkpoints_dir(ctx.name)
        cp_dir.mkdir(parents=True, exist_ok=True)
        cp_file = cp_dir / f"{ts}-{slug}-{cp.uid[:8]}.json"
        if cp_file.exists() or cp_file.is_symlink():
            raise ValueError(
                f"Refusing to replace an existing checkpoint for '{ctx.name}'."
            )
        checkpoint_record = {
            "uid": cp.uid,
            "message": cp.message,
            "timestamp": cp.timestamp.isoformat(),
            "snapshot": cp.snapshot,
            "command": cp.command,
            "args": cp.args,
            "description": cp.description,
            "auto": cp.auto,
        }
        if command_before is not None:
            checkpoint_record["command_before"] = command_before
        _write_json_atomic(cp_file, checkpoint_record)
        return cp

    def list_checkpoints(self, name: str) -> list[dict]:
        """Return checkpoints for a context, sorted newest-first."""
        cp_dir = self._checkpoints_dir(name)
        if not cp_dir.exists():
            return []
        entries = []
        for path in sorted(cp_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            with open(path) as f:
                entries.append(json.load(f))
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)

    def _command_context_archive_path(self, checkpoint_uid: str) -> Path:
        """Resolve one exact creation-command archive without accepting paths."""
        try:
            canonical = str(uuid.UUID(checkpoint_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Command archive checkpoint uid is invalid.") from error
        if canonical != checkpoint_uid:
            raise ValueError("Command archive checkpoint uid is invalid.")
        root = self.command_context_archives_dir
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise ValueError("Command Context archive storage is invalid.")
        return root / checkpoint_uid

    def _load_command_context_archive(
        self,
        checkpoint_uid: str,
    ) -> tuple[Path, dict[str, object], Context, list[dict[str, object]]]:
        """Load one absent Context and its retained checkpoint history."""
        archive = self._command_context_archive_path(checkpoint_uid)
        if archive.is_symlink() or not archive.is_dir():
            raise FileNotFoundError("Command Context archive is unavailable.")
        manifest_path = archive / "manifest.json"
        context_path = archive / "context.json"
        checkpoints_path = archive / "checkpoints"
        for path, label in (
            (manifest_path, "manifest"),
            (context_path, "Context record"),
        ):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Command Context archive {label} is invalid.")
        if checkpoints_path.is_symlink() or not checkpoints_path.is_dir():
            raise ValueError("Command Context archive checkpoints are invalid.")
        with open(manifest_path, encoding="utf-8") as file:
            manifest = json.load(
                file,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        sever_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
            "session_uid",
            "application",
            "reviewing_session_digest",
        }
        lifecycle_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
        }
        atomize_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
            "analysis_uid",
            "source_context_uid",
            "source_context_name",
            "source_workbench",
            "reviewing_workbench_digest",
            "terminal_workbench_digest",
            "current_before",
        }
        if (
            not isinstance(manifest, dict)
            or manifest.get("version") != 1
            or manifest.get("checkpoint_uid") != checkpoint_uid
        ):
            raise ValueError("Command Context archive manifest is invalid.")
        command = manifest.get("command")
        unit_uid = manifest.get("unit_uid")
        if command == "sever":
            if (
                set(manifest) != sever_manifest_fields
                or unit_uid != f"checkpoint:{checkpoint_uid}"
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "merge":
            if (
                set(manifest) != lifecycle_manifest_fields
                or not isinstance(unit_uid, str)
                or not unit_uid.startswith("merge:")
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "branch":
            if (
                set(manifest) != lifecycle_manifest_fields
                or not isinstance(unit_uid, str)
                or not unit_uid.startswith("branch:")
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "atomize":
            if (
                set(manifest) != atomize_manifest_fields
                or unit_uid != f"checkpoint:{checkpoint_uid}"
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        else:
            raise ValueError("Command Context archive manifest is invalid.")
        context_name = manifest.get("context_name")
        context_uid = manifest.get("context_uid")
        if (
            not isinstance(context_name, str)
            or not context_name
            or not isinstance(context_uid, str)
            or not context_uid
        ):
            raise ValueError("Command Context archive manifest is invalid.")
        if command == "sever":
            session_uid = manifest.get("session_uid")
            reviewing_digest = manifest.get("reviewing_session_digest")
            if (
                not isinstance(session_uid, str)
                or not session_uid
                or not isinstance(reviewing_digest, str)
                or len(reviewing_digest) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in reviewing_digest
                )
                or not isinstance(manifest.get("application"), dict)
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "atomize":
            source_context_uid = manifest.get("source_context_uid")
            source_context_name = manifest.get("source_context_name")
            analysis_uid = manifest.get("analysis_uid")
            current_before = manifest.get("current_before")
            if (
                not isinstance(source_context_uid, str)
                or not source_context_uid
                or not isinstance(source_context_name, str)
                or not source_context_name
                or not isinstance(analysis_uid, str)
                or not analysis_uid
                or (current_before is not None and not isinstance(current_before, str))
            ):
                raise ValueError("Command Context archive manifest is invalid.")
            _context_name_parts(source_context_name)
            source_workbench = manifest.get("source_workbench")
            reviewing_digest = manifest.get("reviewing_workbench_digest")
            terminal_digest = manifest.get("terminal_workbench_digest")
            if source_workbench is None:
                if reviewing_digest is not None or terminal_digest is not None:
                    raise ValueError("Command Context archive manifest is invalid.")
            elif (
                not isinstance(source_workbench, dict)
                or not isinstance(reviewing_digest, str)
                or len(reviewing_digest) != 64
                or not isinstance(terminal_digest, str)
                or len(terminal_digest) != 64
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        _context_name_parts(context_name)
        with open(context_path, encoding="utf-8") as file:
            context_record = json.load(
                file,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        context = Context.from_dict(
            _validate_context_header(context_record, context_name)
        )
        if context.uid != context_uid:
            raise ValueError("Command Context archive identity is invalid.")
        entries: list[dict[str, object]] = []
        for path in checkpoints_path.iterdir():
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Command Context archive checkpoints are invalid.")
            with open(path, encoding="utf-8") as file:
                value = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if not isinstance(value, dict):
                raise ValueError("Command Context archive checkpoint is invalid.")
            entries.append(value)
        if not any(entry.get("uid") == checkpoint_uid for entry in entries):
            raise ValueError("Command Context archive lost its source checkpoint.")
        return (
            archive,
            manifest,
            context,
            sorted(entries, key=lambda item: str(item.get("timestamp")), reverse=True),
        )

    def list_command_context_archives(
        self,
    ) -> tuple[tuple[Context, list[dict[str, object]]], ...]:
        """Return validated absent Context histories used by command Undo/Redo."""
        root = self.command_context_archives_dir
        if not root.exists():
            if root.is_symlink():
                raise ValueError("Command Context archive storage is invalid.")
            return ()
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Command Context archive storage is invalid.")
        result: list[tuple[Context, list[dict[str, object]]]] = []
        for path in root.iterdir():
            if path.is_symlink() or not path.is_dir():
                raise ValueError("Command Context archive storage is invalid.")
            _archive, _manifest, context, entries = self._load_command_context_archive(
                path.name
            )
            result.append((context, entries))
        return tuple(sorted(result, key=lambda item: item[0].name))

    @staticmethod
    def _context_for_restoration(
        snapshot: dict[str, object],
        *,
        context_uid: str,
        context_name: str,
        expected_context_digest: str,
    ) -> Context:
        """Build one exact direct restore target under its current owner.

        Revert may select an inherited checkpoint whose serialized owner is a
        branch source, while Undo/Redo carries already-normalized command
        images. Both paths must preserve the live Context identity and attach
        the same compare-and-set digest before publishing through
        ``_save_locked``.
        """

        restored = Context.from_dict(
            {
                **snapshot,
                "uid": context_uid,
                "name": context_name,
            }
        )
        restored._store_digest = expected_context_digest
        return restored

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
            artifact_restore: (
                tuple[Path, dict[str, object], dict[str, object]] | None
            ) = None
            artifact_written = False
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

                    artifact_restore = self._prepare_applied_artifact_restore(
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
                        if artifact_restore is not None:
                            session_path, _session_before, session_after = (
                                artifact_restore
                            )
                            self._write_applied_artifact_restore(
                                session_path,
                                expected=_session_before,
                                value=session_after,
                            )
                            artifact_written = True
                    except Exception:
                        rollback_error: Exception | None = None
                        if artifact_written and artifact_restore is not None:
                            try:
                                session_path, session_before, _session_after = (
                                    artifact_restore
                                )
                                self._write_applied_artifact_restore(
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

    def _remove_checkpoint_uid_locked(self, name: str, checkpoint_uid: str) -> None:
        """Remove one exact provisional checkpoint while its Context is locked."""
        for path in self._checkpoints_dir(name).glob(f"*-{checkpoint_uid[:8]}.json"):
            if path.is_symlink() or not path.is_file():
                continue
            with open(path, encoding="utf-8") as file:
                value = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if value.get("uid") == checkpoint_uid:
                path.unlink()
                return
        raise RuntimeError("Provisional restoration checkpoint is unavailable.")

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

        from memcommit.application.retained_history.command_history import (
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

    def _restore_merge_context_creation_command_locked(self, unit, direction: str):
        """Atomically restore a Merge across updated and created Contexts.

        Created descendants move into the same private, validated lifecycle
        archive used by command history. Updated Contexts are restored in
        place. Every member receives the same restoration receipt, so neither
        a partial tree nor an incomplete redo can enter the global stack.
        """
        from memcommit.application.retained_history.command_history import (
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

    def _restore_atomize_context_creation_command_locked(self, unit, direction: str):
        """Undo/Redo one final Atomize Save As output and its Source receipt."""

        from memcommit.application.operations.atomize.domain import AtomizeAnalysisSession
        from memcommit.application.operations.atomize.workbench import atomize_workbench_record_digest
        from memcommit.application.retained_history.command_history import (
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
                            terminal_digest = atomize_workbench_record_digest(terminal)
                            reviewing = copy.deepcopy(terminal)
                            reviewing.clear_application(
                                output_context_name=change.context_name,
                                checkpoint_uid=change.checkpoint_uid,
                                restore_output_context_name=(
                                    source_workbench_record.get("output_context_name")
                                ),
                            )
                            reviewing_digest = atomize_workbench_record_digest(
                                reviewing
                            )
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
                            if reviewing is None or atomize_workbench_record_digest(
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
                            if atomize_workbench_record_digest(
                                terminal
                            ) != manifest.get("terminal_workbench_digest"):
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
        from memcommit.application.operations.sever.session_store import SeverSessionStore

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

    def _prepare_applied_artifact_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare a saved semantic artifact coupled to one Context command."""
        if unit.command == "meld":
            return self._prepare_meld_command_restore(unit, direction)
        if unit.command == "sever":
            return self._prepare_sever_command_restore(unit, direction)
        if unit.command == "atomize-grounding":
            return self._prepare_atomize_grounding_command_restore(unit, direction)
        if unit.command == "update":
            return self._prepare_update_command_restore(unit, direction)
        return None

    def _prepare_sever_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the Sever-session half of one self-save restoration."""

        if unit.command != "sever" or len(unit.changes) != 1:
            return None
        change = unit.changes[0]
        if change.before is None or change.after is None:
            # Other-save creation uses the dedicated lifecycle restoration.
            return None
        checkpoint = next(
            (
                entry
                for entry in self.list_checkpoints(change.context_name)
                if entry.get("uid") == change.checkpoint_uid
            ),
            None,
        )
        args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
        record = args.get("sever") if isinstance(args, dict) else None
        session_uid = record.get("session_uid") if isinstance(record, dict) else None
        if (
            not isinstance(session_uid, str)
            or record.get("save_mode") != "SELF_SAVE"
            or record.get("source") != change.context_name
            or record.get("output") != change.context_name
        ):
            raise ValueError("Self-save Sever checkpoint has no valid session receipt.")
        from memcommit.application.operations.sever.model import SeverApplication
        from memcommit.application.operations.sever.session_store import SeverSessionStore

        sessions = SeverSessionStore(self)
        session = sessions.load(session_uid)
        result_uids = tuple(
            source.uid for _candidate, source, _content in session.results()
        )
        application = SeverApplication(
            output_context_uid=change.context_uid,
            checkpoint_uid=change.checkpoint_uid,
            result_memory_uids=result_uids,
        )
        if (
            session.save_mode != "SELF_SAVE"
            or session.output_name != change.context_name
            or session.source.root_uid != change.context_uid
        ):
            raise ValueError("Self-save Sever session does not match its command.")
        if direction == "undo":
            if session.state != "APPLIED" or session.application != application:
                raise ConcurrentContextUpdateError(
                    "The self-save Sever session changed before Undo."
                )
            restored = session.clear_application(
                output_context_uid=application.output_context_uid,
                checkpoint_uid=application.checkpoint_uid,
            )
        else:
            if session.state != "REVIEWING" or session.application is not None:
                raise ConcurrentContextUpdateError(
                    "The self-save Sever session changed before Redo."
                )
            restored = session.with_application(application)
        return sessions._path(session.uid), session.to_dict(), restored.to_dict()

    def _write_applied_artifact_restore(
        self,
        path: Path,
        *,
        expected: dict[str, object],
        value: dict[str, object],
    ) -> None:
        """CAS-write one companion artifact inside command restoration."""
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
        from memcommit.application.operations.sever.session_store import SeverSessionStore

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
                    "The applied operation artifact changed during restoration."
                )
            with open(path, encoding="utf-8") as file:
                current = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if current != expected:
                raise ConcurrentContextUpdateError(
                    "The applied operation artifact changed during restoration."
                )
            _write_json_atomic(path, value)

    def _prepare_meld_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the Meld-session half of one Context command restoration."""
        if unit.command != "meld":
            return None
        if not unit.changes:
            raise ValueError("A Meld command has no target Context changes.")
        records: list[dict[str, object]] = []
        for change in unit.changes:
            checkpoint = next(
                (
                    entry
                    for entry in self.list_checkpoints(change.context_name)
                    if entry.get("uid") == change.checkpoint_uid
                ),
                None,
            )
            args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
            record = args.get("meld") if isinstance(args, dict) else None
            if not isinstance(record, dict):
                raise ValueError("Meld checkpoint has no valid session receipt.")
            records.append(record)
        session_uids = {record.get("session_uid") for record in records}
        change_set_digests = {record.get("change_set_digest") for record in records}
        raw_results = records[0].get("results")
        if (
            len(session_uids) != 1
            or len(change_set_digests) != 1
            or not all(isinstance(item, str) and item for item in session_uids)
            or not all(isinstance(item, str) and item for item in change_set_digests)
            or not isinstance(raw_results, list)
            or any(record.get("results") != raw_results for record in records[1:])
        ):
            raise ValueError("Meld checkpoint session receipts are inconsistent.")
        session_uid = next(iter(session_uids))
        change_set_digest = next(iter(change_set_digests))
        result_uids = tuple(
            result.get("memory_uid")
            for result in raw_results
            if isinstance(result, dict) and isinstance(result.get("memory_uid"), str)
        )
        if len(result_uids) != len(raw_results):
            raise ValueError("Meld checkpoint result identities are invalid.")
        target = records[0].get("target_baseline")
        if not isinstance(target, dict):
            raise ValueError("Meld checkpoint target binding is invalid.")
        target_uid = target.get("context_uid")
        target_name = target.get("context_name")
        if not isinstance(target_uid, str) or not isinstance(target_name, str):
            raise ValueError("Meld checkpoint target binding is invalid.")
        session = self.load_meld_session(target_uid)
        if (
            session is None
            or session.uid != session_uid
            or session.target.context_uid != target_uid
            or session.target.context_name != target_name
        ):
            raise ValueError("Meld session does not match the restored command.")
        from memcommit.application.operations.meld.model import (
            MELD_OWNER_AWARE_SCHEMA_VERSION,
            MeldCheckpointReceipt,
        )

        checkpoint_by_identity = {
            (change.context_uid, change.context_name): change.checkpoint_uid
            for change in unit.changes
        }
        baseline = session.frames[1]
        owner_order = (
            tuple((context.uid, context.name) for context in baseline.contexts)
            if baseline.contexts is not None
            else ((target_uid, target_name),)
        )
        receipts = tuple(
            MeldCheckpointReceipt(
                context_uid=context_uid,
                context_name=context_name,
                checkpoint_uid=checkpoint_by_identity[(context_uid, context_name)],
            )
            for context_uid, context_name in owner_order
            if (context_uid, context_name) in checkpoint_by_identity
        )
        if len(receipts) != len(unit.changes):
            raise ValueError("Meld checkpoint owners are outside the target scope.")
        primary_checkpoint_uid = receipts[0].checkpoint_uid
        application_receipts = (
            receipts
            if session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
            else ()
        )
        before = session.to_dict()
        if direction == "undo":
            session.clear_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=primary_checkpoint_uid,
                checkpoints=application_receipts,
            )
        elif session.state == "READY_TO_APPLY" and session.application is None:
            session.record_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=primary_checkpoint_uid,
                result_memory_uids=result_uids,
                checkpoints=application_receipts,
            )
        elif not (
            session.state == "APPLIED"
            and session.application is not None
            and session.application.change_set_digest == change_set_digest
            and session.application.checkpoint_uid == primary_checkpoint_uid
            and session.application.result_memory_uids == result_uids
            and (
                not session.application.checkpoints
                or session.application.checkpoints == receipts
            )
        ):
            raise ValueError("Meld session cannot be restored to applied state.")
        return self._meld_session_path(target_uid), before, session.to_dict()

    def _prepare_atomize_grounding_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]]:
        """Prepare the atomize-grounding session half of Undo or Redo."""
        if len(unit.changes) != 1:
            raise ValueError(
                "An atomize-grounding command must restore exactly one Context."
            )
        change = unit.changes[0]
        checkpoint = next(
            (
                entry
                for entry in self.list_checkpoints(change.context_name)
                if entry.get("uid") == change.checkpoint_uid
            ),
            None,
        )
        args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
        record = args.get("grounding") if isinstance(args, dict) else None
        if not isinstance(record, dict):
            raise ValueError("Atomize grounding checkpoint has no valid receipt.")
        session_uid = record.get("session_uid")
        change_set_digest = record.get("change_set_digest")
        raw_change_set = record.get("change_set")
        if (
            not isinstance(session_uid, str)
            or not session_uid
            or not isinstance(change_set_digest, str)
            or not change_set_digest
            or not isinstance(raw_change_set, dict)
        ):
            raise ValueError("Atomize grounding checkpoint receipt is invalid.")
        raw_proposals = raw_change_set.get("proposals")
        proposal_uids = (
            tuple(
                proposal.get("uid")
                for proposal in raw_proposals
                if isinstance(proposal, dict) and isinstance(proposal.get("uid"), str)
            )
            if isinstance(raw_proposals, list)
            else ()
        )
        if not isinstance(raw_proposals, list) or len(proposal_uids) != len(
            raw_proposals
        ):
            raise ValueError("Atomize grounding proposal identities are invalid.")
        session = self.load_atomize_grounding_session(change.context_uid)
        if (
            session is None
            or session.uid != session_uid
            or session.bindings.context_uid != change.context_uid
            or session.bindings.context_name != change.context_name
        ):
            raise ValueError(
                "Atomize grounding session does not match the restored command."
            )
        before = session.to_dict()
        if direction == "undo":
            session.clear_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=change.checkpoint_uid,
            )
        elif session.state == "READY_TO_APPLY" and session.application is None:
            session.record_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=change.checkpoint_uid,
            )
        elif not (
            session.state == "APPLIED"
            and session.application is not None
            and session.application.change_set_digest == change_set_digest
            and session.application.checkpoint_uid == change.checkpoint_uid
            and session.application.proposal_uids == proposal_uids
        ):
            raise ValueError(
                "Atomize grounding session cannot be restored to applied state."
            )
        return (
            self._atomize_grounding_session_path(change.context_uid),
            before,
            session.to_dict(),
        )

    def _prepare_update_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the active local Update receipt coupled to its checkpoints."""
        from memcommit.application.operations.update.model import operation_digest

        session = self.load_staged_update()
        if session is None:
            # Granted-target Contexts live in the authority Profile; their
            # participant receipt is coordinated by restore_granted_update.
            return None
        digest = operation_digest(session.operations)
        expected_unit_uid = f"update:{session.uid}:{digest}"
        if unit.uid != expected_unit_uid:
            return None
        if session.application is None:
            raise ValueError("Update command has no application receipt.")
        receipt_by_context = {
            (receipt.context_uid, receipt.context_name): receipt.checkpoint_uid
            for receipt in session.application.checkpoints
        }
        command_by_context = {
            (change.context_uid, change.context_name): change.checkpoint_uid
            for change in unit.changes
        }
        if (
            session.application.operation_digest != digest
            or receipt_by_context != command_by_context
        ):
            raise ValueError("Update application receipt does not match this command.")
        before = session.to_dict()
        if direction == "undo":
            session = session.with_restored_application(applied=False)
        elif session.status == "undone":
            session = session.with_restored_application(applied=True)
        elif session.status != "applied":
            raise ValueError("Update session cannot be restored to applied state.")
        return self.staged_update_file, before, session.to_dict()

    def revert(
        self,
        ctx_name: str,
        uid_prefix: str,
        keep_history: bool = True,
        *,
        expected_context_uid: str | None = None,
        expected_context_digest: str | None = None,
        expected_history_digest: str | None = None,
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert one Context while holding its cooperative write lock."""
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            with self._context_write_lock(ctx_name):
                return self._revert_locked(
                    ctx_name,
                    uid_prefix,
                    keep_history=keep_history,
                    expected_context_uid=expected_context_uid,
                    expected_context_digest=expected_context_digest,
                    expected_history_digest=expected_history_digest,
                    revert_unit=None,
                )

    def revert_checkpoint_unit(
        self,
        unit,
        keep_history: bool = True,
    ):
        """Atomically restore every physical member of one checkpoint set.

        The globally resolved unit is freshness-bound, but selection happens
        before the write locks are held.  Revalidate every member before the
        first publication, retain exact Context/history bytes for the outer
        exception rollback, and record one shared Revert command identity so
        Undo/Redo cannot split the recovery unit later.
        """

        from memcommit.application.retained_history.checkpoint_catalog import (
            CheckpointUnitRevertMember,
            CheckpointUnitRevertResult,
            ResolvedCheckpointUnit,
        )

        if not isinstance(unit, ResolvedCheckpointUnit) or not unit.is_recursive_set:
            raise TypeError("Expected one resolved recursive checkpoint unit.")
        if not unit.members:
            raise ValueError("Recursive checkpoint unit has no members.")
        names = tuple(member.context_name for member in unit.members)
        if len(names) != len(set(names)):
            raise ValueError("Recursive checkpoint unit repeats a Context owner.")

        receipt_uid = str(uuid.uuid4())
        command_contexts = [
            {"uid": member.context_uid, "name": member.context_name}
            for member in unit.members
        ]
        revert_unit = {
            "version": 1,
            "receipt_uid": receipt_uid,
            "checkpoint_unit_uid": unit.canonical_uid,
            "checkpoint_set_uid": unit.checkpoint_set_uid,
            "root_context_uid": unit.root_context_uid,
            "root_context_name": unit.root_context_name,
            "contexts": command_contexts,
        }

        with self._command_write_lock():
            self._assert_profile_write_allowed()
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks(names):
                    original_context_bytes: dict[str, bytes] = {}
                    original_checkpoint_bytes: dict[str, dict[str, bytes]] = {}
                    for member in unit.members:
                        current = self.load_direct(member.context_name)
                        entries = self.list_checkpoints(member.context_name)
                        if (
                            current.uid != member.context_uid
                            or context_record_digest(current)
                            != member.expected_context_digest
                            or checkpoint_history_digest(entries)
                            != member.expected_history_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                "A recursive checkpoint member changed after "
                                "the recovery unit was selected."
                            )
                        matches = [
                            entry
                            for entry in entries
                            if entry.get("uid") == member.checkpoint_uid
                        ]
                        if len(matches) != 1 or matches[0] != member.checkpoint:
                            raise ConcurrentContextUpdateError(
                                "A recursive checkpoint member changed after "
                                "the recovery unit was selected."
                            )
                        context_path = self._context_file(member.context_name)
                        checkpoint_dir = self._checkpoints_dir(member.context_name)
                        checkpoint_paths = tuple(sorted(checkpoint_dir.glob("*.json")))
                        if any(
                            path.is_symlink() or not path.is_file()
                            for path in checkpoint_paths
                        ):
                            raise ValueError(
                                f"Checkpoint history for '{member.context_name}' "
                                "is unsafe."
                            )
                        original_context_bytes[member.context_name] = (
                            context_path.read_bytes()
                        )
                        original_checkpoint_bytes[member.context_name] = {
                            path.name: path.read_bytes() for path in checkpoint_paths
                        }

                    published: list[CheckpointUnitRevertMember] = []
                    try:
                        for member in unit.members:
                            recovery, target = self._revert_locked(
                                member.context_name,
                                member.checkpoint_uid,
                                keep_history=keep_history,
                                expected_context_uid=member.context_uid,
                                expected_context_digest=(
                                    member.expected_context_digest
                                ),
                                expected_history_digest=(
                                    member.expected_history_digest
                                ),
                                revert_unit=revert_unit,
                            )
                            published.append(
                                CheckpointUnitRevertMember(
                                    context_name=member.context_name,
                                    target=target,
                                    recovery=recovery,
                                )
                            )
                    except Exception as error:
                        rollback_error: Exception | None = None
                        for member in unit.members:
                            name = member.context_name
                            checkpoint_dir = self._checkpoints_dir(name)
                            originals = original_checkpoint_bytes[name]
                            try:
                                for path in checkpoint_dir.glob("*.json"):
                                    if path.is_symlink() or not path.is_file():
                                        raise ValueError(
                                            f"Checkpoint rollback for '{name}' "
                                            "encountered an unsafe path."
                                        )
                                    if path.name not in originals:
                                        path.unlink()
                                for filename, content in originals.items():
                                    _write_bytes_atomic(
                                        checkpoint_dir / filename,
                                        content,
                                    )
                                _write_bytes_atomic(
                                    self._context_file(name),
                                    original_context_bytes[name],
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Recursive Revert failed and its complete "
                                "Context/history unit could not be restored."
                            ) from rollback_error
                        raise error

        return CheckpointUnitRevertResult(
            unit=unit,
            receipt_uid=receipt_uid,
            members=tuple(published),
        )

    def _revert_locked(
        self,
        ctx_name: str,
        uid_prefix: str,
        *,
        keep_history: bool,
        expected_context_uid: str | None,
        expected_context_digest: str | None,
        expected_history_digest: str | None,
        revert_unit: dict[str, object] | None,
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert context to a checkpoint. Returns (pre_revert_cp, target_cp).

        By default, all checkpoint files remain active and the pre-revert
        snapshot is appended as the new head. Pass ``keep_history=False`` to
        remove checkpoints newer than the target. If that target is itself a
        pre-revert checkpoint carrying a log_snapshot, discard mode rebuilds
        the full original log from that snapshot instead of just truncating.
        """
        entries = self.list_checkpoints(ctx_name)  # captured before any mutations
        # Preconditions and the recovery snapshot concern the directly owned
        # Context record. Do not resolve MemoryRef targets or embedded
        # Contexts merely to decide whether a reviewed frame is still fresh.
        ctx = self.load_direct(ctx_name)
        if expected_context_uid is not None and ctx.uid != expected_context_uid:
            raise ConcurrentContextUpdateError(
                "Context identity changed before the reviewed revert."
            )
        if (
            expected_context_digest is not None
            and context_record_digest(ctx) != expected_context_digest
        ):
            raise ConcurrentContextUpdateError(
                "Context content changed before the reviewed revert."
            )
        if (
            expected_history_digest is not None
            and checkpoint_history_digest(entries) != expected_history_digest
        ):
            raise ConcurrentContextUpdateError(
                "Checkpoint history changed before the reviewed revert."
            )
        matches = [e for e in entries if e["uid"].startswith(uid_prefix)]
        if not matches:
            raise KeyError(f"No checkpoint with uid prefix '{uid_prefix}'.")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous prefix '{uid_prefix}' matches {len(matches)} checkpoints."
            )

        target_data = matches[0]
        target_ts = target_data["timestamp"]
        cp_dir = self._checkpoints_dir(ctx_name)
        checkpoint_paths = tuple(sorted(cp_dir.glob("*.json")))
        if any(path.is_symlink() or not path.is_file() for path in checkpoint_paths):
            raise ValueError(f"Checkpoint history for '{ctx_name}' is unsafe.")
        original_checkpoint_bytes = {
            path.name: path.read_bytes() for path in checkpoint_paths
        }
        physical_records: dict[str, dict[str, object]] = {}
        for path in checkpoint_paths:
            try:
                with open(path, encoding="utf-8") as file:
                    record = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
            except (json.JSONDecodeError, ValueError) as error:
                raise ValueError(
                    f"Checkpoint history for '{ctx_name}' is invalid."
                ) from error
            if not isinstance(record, dict):
                raise ValueError(f"Checkpoint history for '{ctx_name}' is invalid.")
            physical_records[path.name] = record

        restoration_snapshot = target_data["snapshot"]
        if restoration_snapshot.get("uid") != ctx.uid:
            lineage_edges = checkpoint_memory_lineage_edges((entries,))
            restoration_snapshot = remap_restoration_snapshot(
                restoration_snapshot,
                target=ctx,
                edges=lineage_edges,
            )
        restored = self._context_for_restoration(
            restoration_snapshot,
            context_uid=ctx.uid,
            context_name=ctx.name,
            expected_context_digest=context_record_digest(ctx),
        )
        restored_snapshot = restored.to_dict()

        # Strip nested log snapshots so the recovery frame remains bounded.
        thin_entries: list[dict] = []
        for entry in entries:
            args = entry.get("args") or {}
            if "log_snapshot" in args:
                entry = {
                    **entry,
                    "args": {
                        key: value
                        for key, value in args.items()
                        if key != "log_snapshot"
                    },
                }
            thin_entries.append(entry)

        message = f"Pre-revert to [{target_data['uid'][:8]}] — revert here to undo"
        pre_args: dict[str, object] = {
            "target_uid": target_data["uid"],
            "keep_history": keep_history,
            "log_snapshot": thin_entries,
        }
        if revert_unit is not None:
            pre_args["revert_unit"] = copy.deepcopy(revert_unit)
            contexts = revert_unit.get("contexts")
            if not isinstance(contexts, list):
                raise ValueError("Recursive Revert membership is invalid.")
            pre_args["command_contexts"] = copy.deepcopy(contexts)
        pre_cp = Checkpoint(
            uid=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
            command="revert",
            args=pre_args,
            description=message,
            auto=True,
        )
        pre_slug = message[:24].replace(" ", "-").replace("/", "-")
        pre_name = (
            f"{pre_cp.timestamp.strftime('%Y%m%dT%H%M%S')}-"
            f"{pre_slug}-{pre_cp.uid[:8]}.json"
        )
        pre_record: dict[str, object] = {
            "uid": pre_cp.uid,
            "message": pre_cp.message,
            "timestamp": pre_cp.timestamp.isoformat(),
            "snapshot": pre_cp.snapshot,
            "command": pre_cp.command,
            "args": pre_cp.args,
            "description": pre_cp.description,
            "auto": pre_cp.auto,
        }
        if restored_snapshot != target_data["snapshot"]:
            # The selected inherited checkpoint remains authentic Source
            # evidence. Retain the exact Branch-namespace post-image beside
            # the Revert receipt so History, Trace, Undo, Rename, and a later
            # Revert all reconstruct the state that was actually published.
            pre_record["restored_snapshot"] = restored_snapshot

        desired_records: dict[str, dict[str, object]]
        if keep_history:
            desired_records = dict(physical_records)
        else:
            log_snapshot = (target_data.get("args") or {}).get("log_snapshot")
            if log_snapshot is not None:
                if not isinstance(log_snapshot, list):
                    raise ValueError("Checkpoint log snapshot is invalid.")
                desired_records = {}
                for entry in sorted(
                    log_snapshot,
                    key=lambda value: value["timestamp"],
                ):
                    if not isinstance(entry, dict):
                        raise ValueError("Checkpoint log snapshot is invalid.")
                    timestamp = datetime.fromisoformat(entry["timestamp"])
                    uid = entry.get("uid")
                    if not isinstance(uid, str) or not uid:
                        raise ValueError("Checkpoint log snapshot is invalid.")
                    filename = f"{timestamp.strftime('%Y%m%dT%H%M%S')}-{uid[:8]}.json"
                    if filename in desired_records:
                        raise ValueError(
                            "Checkpoint log snapshot contains duplicate entries."
                        )
                    desired_records[filename] = entry
            else:
                desired_records = {
                    filename: record
                    for filename, record in physical_records.items()
                    if record["timestamp"] <= target_ts
                }
        if pre_name in desired_records:
            raise ValueError("Recovery checkpoint filename collided with history.")
        desired_records[pre_name] = pre_record

        context_path = self._context_file(ctx_name)
        original_context_bytes = context_path.read_bytes()
        written_names: set[str] = set()
        try:
            # Prepare every replacement with the normal atomic writer before
            # removing obsolete history. The command lock keeps other history
            # operations outside this exception-rollback boundary.
            for filename, record in desired_records.items():
                destination = cp_dir / filename
                if destination.is_symlink():
                    raise ValueError(
                        f"Refusing to restore checkpoint for '{ctx_name}' "
                        "through a symbolic link."
                    )
                _write_json_atomic(destination, record)
                written_names.add(filename)
            for filename in original_checkpoint_bytes:
                if filename not in desired_records:
                    (cp_dir / filename).unlink()
            self._save_locked(
                restored,
                None,
                expected_context_digest=ctx._store_digest,
            )
        except Exception as error:
            rollback_error: Exception | None = None
            for filename in written_names:
                if filename in original_checkpoint_bytes:
                    continue
                try:
                    path = cp_dir / filename
                    if path.exists() and not path.is_symlink():
                        path.unlink()
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            for filename, content in original_checkpoint_bytes.items():
                try:
                    _write_bytes_atomic(cp_dir / filename, content)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            try:
                _write_bytes_atomic(context_path, original_context_bytes)
            except Exception as candidate:
                rollback_error = rollback_error or candidate
            if rollback_error is not None:
                raise RuntimeError(
                    "Revert failed and its original Context/history could not "
                    "be fully restored."
                ) from rollback_error
            raise error
        restored._store_digest = context_record_digest(restored)

        target_cp = Checkpoint(
            uid=target_data["uid"],
            message=target_data.get("message", ""),
            timestamp=datetime.fromisoformat(target_data["timestamp"]),
            snapshot=restored_snapshot,
            command=target_data.get("command"),
            args=target_data.get("args"),
            description=target_data.get("description"),
            auto=target_data.get("auto", False),
        )
        return pre_cp, target_cp
