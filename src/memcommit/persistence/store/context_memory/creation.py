"""Create ordinary, source-bound, and branched Contexts."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Iterable, Optional

from memcommit.core.context import AutoCheckpoint, Checkpoint, Context, Memory
from memcommit.core.context_targeting.naming import (
    validate_portable_context_name,
)
from memcommit.core.context_navigation import (
    record_current_context_transition,
)
from memcommit.application.capabilities.history.reconstruction.memory_lineage_relations import (
    MemoryLineageEdge,
    memory_content_sha256,
    memory_lineage_record,
)

from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_bytes_atomic,
    _write_json_atomic,
)
from .models import (
    ConcurrentContextUpdateError,
    ContextBranchBinding,
    ContextBranchMemoryBinding,
    _NO_CURRENT_CONTEXT_EXPECTATION,
)
from .records import (
    _context_name_parts,
    _rewrite_branched_checkpoint_record,
    checkpoint_history_digest,
    context_record_digest,
)


class _ContextCreationMixin:
    def create_context(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
    ) -> Checkpoint | None:
        """Create one new Context without overwriting a concurrent owner."""
        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_lock(ctx.name):
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                        expected_context_digest=None,
                        require_new=True,
                    )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def create_context_with_sources(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
        *,
        source_bindings: Iterable[tuple[str, str, str]],
    ) -> Checkpoint | None:
        """Publish a new Context from exact source snapshots.

        The source recheck and require-new write share one lock set.  This is
        the creation counterpart of ``save_context_with_sources`` and prevents
        both stale locators and a concurrent owner from reaching the new path.
        """
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _, _ in bindings)
        if (
            not bindings
            or len(source_names) != len(set(source_names))
            or ctx.name in source_names
        ):
            raise ValueError("Invalid Context creation source lock set.")
        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks((*source_names, ctx.name)):
                    self._assert_source_bindings_locked(bindings)
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                        expected_context_digest=None,
                        require_new=True,
                    )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def create_branch_context(
        self,
        ctx: Context,
        *,
        source_name: str,
        expected_source_uid: str,
        expected_source_digest: str,
        expected_history_digest: str,
        expected_current: str | None,
    ) -> None:
        """Create, inherit history, and select one exact branch atomically."""
        source = self.load_direct(source_name)
        source_memories = tuple(
            item for item in source.iter_items() if isinstance(item, Memory)
        )
        target_memories = tuple(
            item for item in ctx.iter_items() if isinstance(item, Memory)
        )
        if len(source_memories) != len(target_memories) or any(
            source_item.content != target_item.content
            for source_item, target_item in zip(
                source_memories,
                target_memories,
                strict=True,
            )
        ):
            raise ValueError("Branch target Memories do not match the Source frame.")
        self.create_branch_contexts(
            (
                ContextBranchBinding(
                    source_name=source_name,
                    expected_source_uid=expected_source_uid,
                    expected_source_digest=expected_source_digest,
                    expected_history_digest=expected_history_digest,
                    target=ctx,
                    memories=tuple(
                        ContextBranchMemoryBinding(
                            source_uid=source_item.uid,
                            target_uid=target_item.uid,
                            source_content_sha256=memory_content_sha256(
                                source_item.content
                            ),
                            target_content_sha256=memory_content_sha256(
                                target_item.content
                            ),
                        )
                        for source_item, target_item in zip(
                            source_memories,
                            target_memories,
                            strict=True,
                        )
                    ),
                ),
            ),
            source_root=source_name,
            target_root=ctx.name,
            include_descendants=False,
            expected_current=expected_current,
        )

    def create_branch_contexts(
        self,
        bindings: Iterable[ContextBranchBinding],
        *,
        source_root: str,
        target_root: str,
        include_descendants: bool,
        expected_current: str | None,
    ) -> None:
        """Publish one exact or lexical-subtree Branch as a single command.

        The complete Source membership, every record and checkpoint history,
        every require-new destination, and current selection remain frozen
        from final validation through publication and exception rollback.
        """
        records = tuple(bindings)
        if not records:
            raise ValueError("A Branch requires at least one Context binding.")
        if type(include_descendants) is not bool:
            raise ValueError("Branch descendant scope must be a boolean.")
        _context_name_parts(source_root)
        validate_portable_context_name(target_root)
        if source_root == target_root:
            raise ValueError("A Branch must have a new Context root name.")

        source_names = tuple(binding.source_name for binding in records)
        target_names = tuple(binding.target.name for binding in records)
        for target_name in target_names:
            validate_portable_context_name(target_name)
        if (
            len(source_names) != len(set(source_names))
            or len(target_names) != len(set(target_names))
            or set(source_names) & set(target_names)
            or source_root not in source_names
            or target_root not in target_names
        ):
            raise ValueError("Invalid Branch Source or target binding set.")
        if not include_descendants and len(records) != 1:
            raise ValueError("An exact Branch must create exactly one Context.")

        for binding in records:
            source_memory_uids = tuple(item.source_uid for item in binding.memories)
            target_memory_uids = tuple(item.target_uid for item in binding.memories)
            target_memories = {
                item.uid: item
                for item in binding.target.iter_items()
                if isinstance(item, Memory)
            }
            if (
                len(source_memory_uids) != len(set(source_memory_uids))
                or len(target_memory_uids) != len(set(target_memory_uids))
                or set(source_memory_uids) & set(target_memory_uids)
                or set(target_memory_uids) != set(target_memories)
            ):
                raise ValueError("Branch Memory occurrence mapping is invalid.")
            for item in binding.memories:
                target_memory = target_memories.get(item.target_uid)
                if (
                    not isinstance(target_memory, Memory)
                    or memory_content_sha256(target_memory.content)
                    != item.target_content_sha256
                    or item.source_content_sha256 != item.target_content_sha256
                ):
                    raise ValueError(
                        "Branch Memory occurrence mapping does not match its target."
                    )

        expected_targets = {
            source_name: target_root + source_name[len(source_root) :]
            for source_name in source_names
            if source_name == source_root or source_name.startswith(source_root + "/")
        }
        if len(expected_targets) != len(records) or any(
            binding.target.name != expected_targets.get(binding.source_name)
            for binding in records
        ):
            raise ValueError("Branch targets must preserve Source subtree suffixes.")
        source_uids = {binding.expected_source_uid for binding in records}
        if len({binding.target.uid for binding in records}) != len(records) or any(
            binding.target.uid in source_uids for binding in records
        ):
            raise ValueError("Every Branch Context requires one new identity.")
        targets_by_source_uid = {
            binding.expected_source_uid: (
                binding.target.uid,
                binding.target.name,
            )
            for binding in records
        }
        operation_uid = str(uuid.uuid4())
        command_contexts = [
            {
                "uid": binding.target.uid,
                "name": binding.target.name,
            }
            for binding in records
        ]
        branch_tree = {
            "version": 1,
            "operation_uid": operation_uid,
            "source_root": source_root,
            "target_root": target_root,
            "include_descendants": include_descendants,
            "current_before": expected_current,
            "contexts": [
                {
                    "source_uid": binding.expected_source_uid,
                    "source_name": binding.source_name,
                    "target_uid": binding.target.uid,
                    "target_name": binding.target.name,
                }
                for binding in records
            ],
        }
        branch_memory_lineage = memory_lineage_record(
            operation_uid,
            (
                MemoryLineageEdge(
                    source_context_uid=binding.expected_source_uid,
                    source_memory_uid=memory.source_uid,
                    target_context_uid=binding.target.uid,
                    target_memory_uid=memory.target_uid,
                    source_content_sha256=memory.source_content_sha256,
                    target_content_sha256=memory.target_content_sha256,
                )
                for binding in records
                for memory in binding.memories
            ),
        )
        branch_description = (
            f"Branched subtree '{source_root}' to '{target_root}'."
            if include_descendants
            else f"Branched '{source_root}' to '{target_root}'."
        )

        source_receipts = tuple(
            (
                binding.source_name,
                binding.expected_source_uid,
                binding.expected_source_digest,
            )
            for binding in records
        )
        lock_names = (*source_names, *target_names)
        with self._command_write_lock():
            # Subtree membership is itself part of the reviewed request. An
            # exclusive graph lock prevents a new lexical descendant from
            # appearing after the final membership recheck.
            with self._context_graph_lock(exclusive=include_descendants):
                with self._context_write_locks(lock_names):
                    if include_descendants:
                        from memcommit.core.context_targeting.model import ContextScope
                        from memcommit.core.context_targeting.resolution import (
                            expand_lexical_context_names,
                        )

                        live_source_names = expand_lexical_context_names(
                            ContextScope.create(
                                (source_root,),
                                include_descendants=True,
                            ),
                            self.list_context_names(),
                        )
                        if live_source_names != source_names:
                            raise ConcurrentContextUpdateError(
                                "The Source Context subtree changed before the "
                                "Branch could be created."
                            )
                    self._assert_source_bindings_locked(
                        source_receipts,
                        result_label="branch",
                    )
                    for binding in records:
                        live_source = self.load_direct(binding.source_name)
                        live_memories = {
                            item.uid: item
                            for item in live_source.iter_items()
                            if isinstance(item, Memory)
                        }
                        if set(live_memories) != {
                            item.source_uid for item in binding.memories
                        }:
                            raise ConcurrentContextUpdateError(
                                "The Branch Source Memory membership changed before "
                                "publication."
                            )
                        for item in binding.memories:
                            source_memory = live_memories[item.source_uid]
                            if (
                                memory_content_sha256(source_memory.content)
                                != item.source_content_sha256
                            ):
                                raise ConcurrentContextUpdateError(
                                    "A Branch Source Memory changed before publication."
                                )

                    checkpoint_files: dict[
                        str,
                        tuple[tuple[Path, dict[str, object] | None], ...],
                    ] = {}
                    for binding in records:
                        history = self.list_checkpoints(binding.source_name)
                        if (
                            checkpoint_history_digest(history)
                            != binding.expected_history_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Checkpoint history for '{binding.source_name}' "
                                "changed before the branch could be created."
                            )
                        source_checkpoints = self._checkpoints_dir(binding.source_name)
                        files: tuple[Path, ...] = ()
                        if source_checkpoints.exists():
                            if (
                                source_checkpoints.is_symlink()
                                or not source_checkpoints.is_dir()
                            ):
                                raise ValueError(
                                    f"Checkpoint history for "
                                    f"'{binding.source_name}' is unsafe."
                                )
                            files = tuple(sorted(source_checkpoints.iterdir()))
                            if any(
                                path.is_symlink()
                                or not path.is_file()
                                or path.suffix != ".json"
                                for path in files
                            ):
                                raise ValueError(
                                    f"Checkpoint history for "
                                    f"'{binding.source_name}' is unsafe."
                                )
                        prepared_files: list[tuple[Path, dict[str, object] | None]] = []
                        for path in files:
                            rewritten: dict[str, object] | None = None
                            if include_descendants:
                                try:
                                    with open(path, encoding="utf-8") as file:
                                        raw = json.load(
                                            file,
                                            object_pairs_hook=(
                                                _reject_duplicate_json_keys
                                            ),
                                        )
                                except (json.JSONDecodeError, ValueError) as error:
                                    raise ValueError(
                                        f"Checkpoint history for "
                                        f"'{binding.source_name}' is invalid."
                                    ) from error
                                if not isinstance(raw, dict):
                                    raise ValueError(
                                        f"Checkpoint history for "
                                        f"'{binding.source_name}' is invalid."
                                    )
                                rewritten = _rewrite_branched_checkpoint_record(
                                    raw,
                                    targets_by_source_uid=targets_by_source_uid,
                                )
                            prepared_files.append((path, rewritten))
                        checkpoint_files[binding.source_name] = tuple(prepared_files)

                    for target_name in target_names:
                        if self.context_exists(target_name):
                            self.load_direct(target_name)
                            raise FileExistsError(
                                f"Context '{target_name}' already exists."
                            )
                        self._assert_context_storage_available(target_name)

                    created: list[Context] = []
                    branch_error: Exception | None = None
                    with self._state_write_lock():
                        state = self._read_state()
                        if state.get("current") != expected_current:
                            raise ConcurrentContextUpdateError(
                                "The current Context changed before the branch "
                                "could be created."
                            )
                        try:
                            for binding in records:
                                target = binding.target
                                self._save_locked(
                                    target,
                                    None,
                                    expected_context_digest=None,
                                    require_new=True,
                                )
                                created.append(target)
                                target_checkpoints = self._checkpoints_dir(target.name)
                                for source_path, rewritten in checkpoint_files[
                                    binding.source_name
                                ]:
                                    destination = target_checkpoints / source_path.name
                                    if destination.exists() or destination.is_symlink():
                                        raise FileExistsError(
                                            f"Branch checkpoint destination for "
                                            f"'{target.name}' already exists."
                                        )
                                    if rewritten is None:
                                        _write_bytes_atomic(
                                            destination,
                                            source_path.read_bytes(),
                                        )
                                    else:
                                        _write_json_atomic(destination, rewritten)
                                checkpoint = self._save_locked(
                                    target,
                                    AutoCheckpoint(
                                        command="branch",
                                        args={
                                            "branch_tree": branch_tree,
                                            "command_contexts": command_contexts,
                                            "memory_lineage": branch_memory_lineage,
                                        },
                                        description=branch_description,
                                    ),
                                    expected_context_digest=context_record_digest(
                                        target
                                    ),
                                )
                                if checkpoint is None:
                                    raise RuntimeError(
                                        "Branch creation recorded no command "
                                        "checkpoint."
                                    )
                            record_current_context_transition(state, target_root)
                            self._write_state(state)
                        except Exception as error:
                            branch_error = error
                    if branch_error is not None:
                        rollback_error: Exception | None = None
                        for target in reversed(created):
                            try:
                                self._delete_locked(target.name)
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Branch creation failed and its new Context "
                                "hierarchy could not be fully rolled back."
                            ) from rollback_error
                        raise branch_error
        for binding in records:
            binding.target._store_digest = context_record_digest(binding.target)

    def create_missing_contexts(
        self,
        entries: Iterable[tuple[Context, Optional[AutoCheckpoint]]],
        *,
        make_current: str | None = None,
        require_all_new: bool = False,
        expected_current: str | None | object = _NO_CURRENT_CONTEXT_EXPECTATION,
    ) -> tuple[Context, ...]:
        """Create one namespace batch and optionally CAS-select its target."""
        with self._command_write_lock():
            return self._create_missing_contexts_command_locked(
                entries,
                make_current=make_current,
                require_all_new=require_all_new,
                expected_current=expected_current,
            )

    def _create_missing_contexts_command_locked(
        self,
        entries: Iterable[tuple[Context, Optional[AutoCheckpoint]]],
        *,
        make_current: str | None = None,
        require_all_new: bool = False,
        expected_current: str | None | object = _NO_CURRENT_CONTEXT_EXPECTATION,
    ) -> tuple[Context, ...]:
        """Create a validated batch and optionally select one batch Context.

        All names stay locked from preflight through rollback. This matters
        for namespace-parent creation: releasing an earlier parent lock before
        a later child fails could let another process modify that new parent,
        which a command-level rollback might then wrongly delete. Selection
        stays inside the same boundary so a new leaf cannot be deleted or
        replaced between its creation and the state write.

        ``require_all_new`` is used by exact creation and identity-preserving
        import: silently reusing one existing name would turn a reviewed
        all-new batch into a different operation. When supplied,
        ``expected_current`` prevents a long interactive creation flow from
        overwriting a later Context switch at the final state write.
        """
        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context is required.")
        if any(not isinstance(context, Context) for context, _ in records):
            raise TypeError("Expected Context records.")
        names = tuple(context.name for context, _ in records)
        for name in names:
            validate_portable_context_name(name)
        if len(names) != len(set(names)):
            raise ValueError("Context batch contains duplicate names.")
        if make_current is not None and make_current not in names:
            raise ValueError("Selected Context must be part of the creation batch.")

        with self._context_graph_lock(exclusive=False):
            with self._context_write_locks(names):
                existing: set[str] = set()
                for name in names:
                    if self.context_exists(name):
                        # A present file is not reusable until its stored identity
                        # and path-bound header have passed normal validation.
                        self.load_direct(name)
                        existing.add(name)
                    else:
                        self._assert_context_storage_available(name)

                if require_all_new and existing:
                    raise FileExistsError(
                        "Context destination already exists: "
                        + ", ".join(sorted(existing))
                    )

                created: list[Context] = []
                try:
                    for context, auto_checkpoint in records:
                        if context.name in existing:
                            continue
                        self._save_locked(
                            context,
                            auto_checkpoint,
                            expected_context_digest=None,
                            require_new=True,
                        )
                        context._store_digest = context_record_digest(context)
                        created.append(context)
                    if make_current is not None:
                        with self._state_write_lock():
                            state = self._read_state()
                            if (
                                expected_current is not _NO_CURRENT_CONTEXT_EXPECTATION
                                and state.get("current") != expected_current
                            ):
                                raise ConcurrentContextUpdateError(
                                    "The current Context changed before the new "
                                    "Context could be selected."
                                )
                            record_current_context_transition(state, make_current)
                            self._write_state(state)
                except Exception as error:
                    rollback_error: Exception | None = None
                    for context in reversed(created):
                        try:
                            self._delete_locked(context.name)
                        except Exception as candidate:
                            rollback_error = candidate
                            break
                    if rollback_error is not None:
                        raise RuntimeError(
                            "Context hierarchy creation failed and its newly "
                            "created Contexts could not be rolled back."
                        ) from rollback_error
                    raise error
        return tuple(created)
