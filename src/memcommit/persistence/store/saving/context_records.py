"""Save existing Context records and command batches."""

from __future__ import annotations

import json
from typing import Iterable, Optional

from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.checkpoint import Checkpoint
from memcommit.models.context import Context
from memcommit.core.context_name_validation import validate_context_name

from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)
from ..context_memory.models import ConcurrentContextUpdateError
from ..context_memory.records import _validate_context_header


class _ContextSavingMixin:
    def save(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpointRequest] = None,
    ) -> Checkpoint | None:
        """Persist one Context inside the global command-order boundary."""
        with self._command_write_lock():
            return self._save_command_locked(
                ctx,
                auto_checkpoint,
            )

    def _save_command_locked(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpointRequest] = None,
    ) -> Checkpoint | None:
        """Persist a Context and its optional checkpoint."""
        # Coordinate new names with namespace changes; writing and checkpointing
        # still share the same Context lock and exception rollback boundary.
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(ctx.name):
                checkpoint = self._save_locked(ctx, auto_checkpoint)
        return checkpoint

    def save_context_command_batch(
        self,
        entries: Iterable[tuple[Context, AutoCheckpointRequest]],
        *,
        source_bindings: Iterable[tuple[str, str]] = (),
        expected_context_catalog: Iterable[str] | None = None,
    ) -> tuple[Checkpoint, ...]:
        """Persist one existing multi-Context command with exception rollback.

        Each entry carries a Context and its checkpoint request. The complete
        identity set stays locked through the final write. Rollback protects
        ordinary exceptions; a durable crash journal remains deferred.
        """

        with self._command_write_lock():
            return self._save_context_command_batch_command_locked(
                entries,
                source_bindings=source_bindings,
                expected_context_catalog=expected_context_catalog,
            )

    def _save_context_command_batch_command_locked(
        self,
        entries: Iterable[tuple[Context, AutoCheckpointRequest]],
        *,
        source_bindings: Iterable[tuple[str, str]] = (),
        expected_context_catalog: Iterable[str] | None = None,
    ) -> tuple[Checkpoint, ...]:
        """Reuse batch persistence when a coordinating operation owns the lock."""
        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context command entry is required.")
        if any(
            not isinstance(context, Context)
            or not isinstance(checkpoint, AutoCheckpointRequest)
            for context, checkpoint in records
        ):
            raise TypeError("Invalid Context command batch entry.")
        names = tuple(context.name for context, _ in records)
        if len(names) != len(set(names)):
            raise ValueError("Context command batch contains duplicate names.")
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _uid in bindings)
        if len(source_names) != len(set(source_names)):
            raise ValueError("Context command batch repeats a source binding.")
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(uid, str)
            or not uid
            for name, uid in bindings
        ):
            raise TypeError("Invalid Context command source binding.")
        for name in names:
            validate_context_name(name)
        for name in source_names:
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
            raise ValueError("Expected Context command catalog is invalid.")

        # A complete-scope operation may bind catalog membership as well
        # as Context bytes. Use the exclusive graph lock only for those
        # callers; ordinary batches retain the narrower shared lock.
        with self._context_graph_lock(exclusive=expected_catalog is not None):
            if (
                expected_catalog is not None
                and tuple(self.list_context_names()) != expected_catalog
            ):
                raise ConcurrentContextUpdateError(
                    "The Context namespace changed after the command was reviewed."
                )
            # Read-only members of a complete operation frame stay locked
            # through the writes as well. Otherwise a plan claiming all
            # matches could silently miss a newly changed sibling.
            with self._context_write_locks((*names, *source_names)):
                if bindings:
                    self._assert_source_bindings_locked(
                        bindings,
                        result_label="Context command batch",
                    )
                original_records: dict[str, dict[str, object]] = {}
                for context, _ in records:
                    try:
                        current = self.load_direct(context.name)
                    except FileNotFoundError as error:
                        raise ConcurrentContextUpdateError(
                            f"Context '{context.name}' no longer exists."
                        ) from error
                    if (
                        current.uid != context.uid
                    ):
                        raise ConcurrentContextUpdateError(
                            f"Context '{context.name}' changed before the "
                            "command could be saved."
                        )
                    # Validate the entire write set before the first
                    # publication. Rollback still protects unexpected I/O
                    # failures, while a locked later Context must fail the
                    # complete command without a provisional earlier save.
                    self._assert_context_record_change_allowed(
                        current,
                        context,
                    )
                    original_records[context.name] = current.to_dict()

                created: list[tuple[str, Checkpoint]] = []
                written: list[str] = []
                try:
                    for context, auto_checkpoint in records:
                        checkpoint = self._save_locked(
                            context,
                            auto_checkpoint,
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Context command batch created no checkpoint."
                            )
                        written.append(context.name)
                        created.append((context.name, checkpoint))
                except Exception:
                    rollback_error: Exception | None = None
                    for name in written:
                        try:
                            _write_json_atomic(
                                self._context_file(name),
                                original_records[name],
                            )
                        except Exception as candidate:
                            rollback_error = rollback_error or candidate
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
                            "Context command batch failed and could not be "
                            "fully rolled back."
                        ) from rollback_error
                    raise

        return tuple(checkpoint for _, checkpoint in created)

    def save_merge_target(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpointRequest,
        *,
        require_new: bool = False,
        source_bindings: Iterable[tuple[str, str]],
    ) -> Checkpoint | None:
        """Save one Merge result as one globally ordered command."""
        with self._command_write_lock():
            return self._save_merge_target_command_locked(
                ctx,
                auto_checkpoint,
                require_new=require_new,
                source_bindings=source_bindings,
            )

    def _save_merge_target_command_locked(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpointRequest,
        *,
        require_new: bool = False,
        source_bindings: Iterable[tuple[str, str]],
    ) -> Checkpoint | None:
        """Publish a Merge target while its Source identities stay locked."""
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _ in bindings)
        if len(source_names) != len(set(source_names)) or ctx.name in source_names:
            raise ValueError("Invalid Merge source lock set.")
        with self._context_graph_lock(exclusive=require_new):
            with self._context_write_locks((*source_names, ctx.name)):
                self._assert_source_bindings_locked(
                    bindings,
                    result_label="Merge target",
                )
                record = auto_checkpoint.command_details.get("merge", {})
                operation_uid = record.get("operation_uid")
                if (
                    operation_uid
                    and self.context_exists(ctx.name)
                    and any(
                        entry.get("command_details", {}).get("merge", {}).get("operation_uid")
                        == operation_uid
                        for entry in self.list_checkpoints(ctx.name)
                    )
                ):
                    raise ConcurrentContextUpdateError(
                        "This Merge proposal was already applied."
                    )
                checkpoint = self._save_locked(
                    ctx,
                    auto_checkpoint,
                    require_new=require_new,
                )
        return checkpoint

    def save_context_with_sources(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpointRequest,
        *,
        source_bindings: Iterable[tuple[str, str]],
    ) -> Checkpoint | None:
        """Save a target with its exact Source identities locked."""
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _ in bindings)
        if not bindings or len(source_names) != len(set(source_names)):
            raise ValueError("Invalid Context source lock set.")
        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks((*source_names, ctx.name)):
                    self._assert_source_bindings_locked(bindings)
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                    )
        return checkpoint

    def _assert_source_bindings_locked(
        self,
        bindings: Iterable[tuple[str, str]],
        *,
        result_label: str = "result",
    ) -> None:
        """Validate exact source identities while their write locks are held."""
        if not result_label:
            raise ValueError("Context source result label cannot be empty.")
        for name, expected_uid in bindings:
            try:
                source = self.load_direct(name)
            except FileNotFoundError as error:
                raise ConcurrentContextUpdateError(
                    f"The source Context no longer exists: '{name}'."
                ) from error
            if (
                source.uid != expected_uid
            ):
                raise ConcurrentContextUpdateError(
                    f"The source Context changed before the {result_label} "
                    f"could be saved: '{name}'."
                )

    def _save_locked(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpointRequest],
        *,
        require_new: bool = False,
    ) -> Checkpoint | None:
        """Save while holding this Context's cooperative process lock."""
        self._assert_profile_write_allowed()
        ctx_dir = self._context_dir(ctx.name)
        context_file = self._context_file(ctx.name)
        if context_file.is_symlink():
            raise ValueError(
                f"Refusing to write context '{ctx.name}' through a symbolic link."
            )
        context_preexisting = self.context_exists(ctx.name)
        if require_new and context_preexisting:
            raise FileExistsError(f"Context '{ctx.name}' already exists.")
        current_record: dict[str, object] | None = None
        if context_preexisting:
            with open(context_file, encoding="utf-8") as file:
                loaded_record = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            current_record = _validate_context_header(
                loaded_record,
                ctx.name,
            )
        if current_record is not None:
            self._assert_context_record_change_allowed(current_record, ctx)
        if not context_preexisting:
            self._assert_context_storage_available(ctx.name)
        ctx_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir = self._checkpoints_dir(ctx.name)
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        created_checkpoint: Checkpoint | None = None
        try:
            if auto_checkpoint is not None:
                # _save_locked already owns the Context lock. Calling the
                # public locking wrapper here would deadlock on flock, while
                # writing without this shared lock would let checkpoint
                # history race reviewed revert/undo selections.
                created_checkpoint = self._checkpoint_locked(
                    ctx,
                    command=auto_checkpoint.command,
                    command_details=auto_checkpoint.command_details,
                    auto=True,
                    command_before=current_record,
                )
            _write_json_atomic(context_file, ctx.to_dict())
        except Exception as error:
            cleanup_error: Exception | None = None
            if created_checkpoint is not None:
                try:
                    matches = list(
                        checkpoints_dir.glob(f"*-{created_checkpoint.uid[:8]}.json")
                    )
                    for path in matches:
                        if path.is_symlink() or not path.is_file():
                            continue
                        with open(path) as f:
                            value = json.load(f)
                        if value.get("uid") == created_checkpoint.uid:
                            path.unlink()
                            break
                except Exception as candidate:
                    cleanup_error = candidate
            if not context_preexisting and not context_file.exists():
                try:
                    checkpoints_dir.rmdir()
                    self._prune_empty_namespace_dirs(ctx_dir)
                except OSError:
                    # A pre-existing child namespace or an unexpected artifact
                    # is never removed as part of rollback.
                    pass
            if cleanup_error is not None:
                raise RuntimeError(
                    "Context save failed and its automatic checkpoint could "
                    "not be rolled back."
                ) from cleanup_error
            raise error
        return created_checkpoint
