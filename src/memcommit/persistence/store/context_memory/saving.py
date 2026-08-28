"""Save existing Context records and command batches."""

from __future__ import annotations

import json
from typing import Iterable, Optional

from memcommit.core.context import AutoCheckpoint, Checkpoint, Context
from memcommit.core.context_targeting.naming import (
    validate_portable_context_name,
)

from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)
from .models import ConcurrentContextUpdateError
from .records import (
    _validate_context_header,
    context_record_digest,
    validate_context_name,
)


class _ContextSavingMixin:
    def save(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
        *,
        expected_context_digest: str | None = None,
    ) -> Checkpoint | None:
        """Persist one Context inside the global command-order boundary."""
        with self._command_write_lock():
            return self._save_command_locked(
                ctx,
                auto_checkpoint,
                expected_context_digest=expected_context_digest,
            )

    def _save_command_locked(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
        *,
        expected_context_digest: str | None = None,
    ) -> Checkpoint | None:
        """Persist a Context, optionally only if its disk record is unchanged."""
        if expected_context_digest is None:
            expected_context_digest = getattr(ctx, "_store_digest", None)
        # A brand-new identity can add an inbound reference under a name that
        # did not exist during rename's graph scan. Coordinate that creation
        # with the graph lock; stale loaded writers already carry a digest and
        # are rejected by ordinary per-Context CAS after a rename.
        if expected_context_digest is None:
            with self._context_graph_lock(exclusive=False):
                with self._context_write_lock(ctx.name):
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                        expected_context_digest=expected_context_digest,
                    )
        else:
            with self._context_write_lock(ctx.name):
                checkpoint = self._save_locked(
                    ctx,
                    auto_checkpoint,
                    expected_context_digest=expected_context_digest,
                )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def save_context_command_batch(
        self,
        entries: Iterable[tuple[Context, AutoCheckpoint, str]],
        *,
        source_bindings: Iterable[tuple[str, str, str]] = (),
        expected_context_catalog: Iterable[str] | None = None,
    ) -> tuple[Checkpoint, ...]:
        """Persist one existing multi-Context command with exception rollback.

        Each entry carries its own already-reviewed Context digest.  The
        complete name set remains locked from the first revalidation through
        the final write, so application adapters can publish a command unit
        without inventing a whole-graph digest.  This is exception-atomic;
        like the other multi-Context prototype paths, a durable crash journal
        is intentionally deferred.
        """

        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context command entry is required.")
        if any(
            not isinstance(context, Context)
            or not isinstance(checkpoint, AutoCheckpoint)
            or not isinstance(expected_digest, str)
            for context, checkpoint, expected_digest in records
        ):
            raise TypeError("Invalid Context command batch entry.")
        names = tuple(context.name for context, _, _ in records)
        if len(names) != len(set(names)):
            raise ValueError("Context command batch contains duplicate names.")
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _uid, _digest in bindings)
        if len(source_names) != len(set(source_names)):
            raise ValueError("Context command batch repeats a source binding.")
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(uid, str)
            or not uid
            or not isinstance(digest, str)
            or not digest
            for name, uid, digest in bindings
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

        with self._command_write_lock():
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
                    for context, _, expected_digest in records:
                        try:
                            current = self.load_direct(context.name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' no longer exists."
                            ) from error
                        if (
                            current.uid != context.uid
                            or context_record_digest(current) != expected_digest
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
                        for context, auto_checkpoint, expected_digest in records:
                            checkpoint = self._save_locked(
                                context,
                                auto_checkpoint,
                                expected_context_digest=expected_digest,
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

        for context, _, _ in records:
            context._store_digest = context_record_digest(context)
        return tuple(checkpoint for _, checkpoint in created)

    def save_meld_target(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpoint,
        *,
        expected_context_digest: str,
        source_bindings: Iterable[tuple[str, str, str]],
    ) -> Checkpoint | None:
        """Save one Meld result as one globally ordered command."""
        with self._command_write_lock():
            return self._save_meld_target_command_locked(
                ctx,
                auto_checkpoint,
                expected_context_digest=expected_context_digest,
                source_bindings=source_bindings,
            )

    def _save_meld_target_command_locked(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpoint,
        *,
        expected_context_digest: str,
        source_bindings: Iterable[tuple[str, str, str]],
    ) -> Checkpoint | None:
        """Save one meld target while its exact source snapshots stay locked.

        Ordinary Context CAS protects only the target. A meld result also
        depends on read-only source snapshots, so all participating Context
        locks must remain held from the final source recheck through the
        target checkpoint and write. In a directional meld the BASELINE frame
        is the target itself and is protected by target CAS rather than being
        repeated in ``source_bindings``.
        """
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _, _ in bindings)
        if len(source_names) != len(set(source_names)) or ctx.name in source_names:
            raise ValueError("Invalid meld source lock set.")
        with self._context_graph_lock(exclusive=False):
            with self._context_write_locks((*source_names, ctx.name)):
                self._assert_source_bindings_locked(
                    bindings,
                    result_label="meld target",
                )
                checkpoint = self._save_locked(
                    ctx,
                    auto_checkpoint,
                    expected_context_digest=expected_context_digest,
                )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def save_context_with_sources(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpoint,
        *,
        expected_context_digest: str,
        source_bindings: Iterable[tuple[str, str, str]],
    ) -> Checkpoint | None:
        """Save a target only while every source receipt is still exact.

        A target digest cannot detect a rename or replacement of a separate
        source that supplied a persisted locator.  Keep every source and the
        target locked from final validation through the target write so a
        successful command cannot reintroduce stale source names.
        """
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _, _ in bindings)
        if not bindings or len(source_names) != len(set(source_names)):
            raise ValueError("Invalid Context source lock set.")
        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks((*source_names, ctx.name)):
                    self._assert_source_bindings_locked(bindings)
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                        expected_context_digest=expected_context_digest,
                    )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def _assert_source_bindings_locked(
        self,
        bindings: Iterable[tuple[str, str, str]],
        *,
        result_label: str = "result",
    ) -> None:
        """Validate exact source identities while their write locks are held."""
        if not result_label:
            raise ValueError("Context source result label cannot be empty.")
        for name, expected_uid, expected_digest in bindings:
            try:
                source = self.load_direct(name)
            except FileNotFoundError as error:
                raise ConcurrentContextUpdateError(
                    f"The source Context no longer exists: '{name}'."
                ) from error
            if (
                source.uid != expected_uid
                or context_record_digest(source) != expected_digest
            ):
                raise ConcurrentContextUpdateError(
                    f"The source Context changed before the {result_label} "
                    f"could be saved: '{name}'."
                )

    def _save_locked(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint],
        *,
        expected_context_digest: str | None,
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
        if not context_preexisting:
            # Existing non-portable records remain writable until an explicit
            # identity-preserving migration moves them. A newly published
            # identity must never reintroduce shell-dependent spelling.
            validate_portable_context_name(ctx.name)
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
        if expected_context_digest is not None:
            if len(expected_context_digest) != 64 or any(
                character not in "0123456789abcdef"
                for character in expected_context_digest
            ):
                raise ValueError("Expected Context digest is invalid.")
            if not context_preexisting:
                raise ConcurrentContextUpdateError(
                    f"Context '{ctx.name}' no longer exists."
                )
            assert current_record is not None
            if context_record_digest(current_record) != expected_context_digest:
                raise ConcurrentContextUpdateError(
                    f"Context '{ctx.name}' changed before it could be saved."
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
                    message=auto_checkpoint.description,
                    command=auto_checkpoint.command,
                    args=auto_checkpoint.args,
                    description=auto_checkpoint.description,
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
