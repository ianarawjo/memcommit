"""Create ordinary, source-bound, and branched Contexts."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Iterable, Optional

from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.checkpoint import Checkpoint
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.core.context_name_validation import validate_context_name
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
from .records import validate_checkpoint_context_frames, checkpoint_history_digest
from ..context_hierarchy import (
    prepare_context_creation_entries,
    validate_context_hierarchy,
)


class _ContextCreationMixin:
    def create_context(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpointRequest] = None,
    ) -> Checkpoint | None:
        """Create one new Context without overwriting a concurrent owner."""
        _, checkpoints = self._create_contexts_with_ancestors(
            ((ctx, auto_checkpoint),), require_all_new=True
        )
        return checkpoints.get(ctx.name)

    def create_context_with_sources(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpointRequest] = None,
        *,
        source_bindings: Iterable[tuple[str, str]],
        expected_context_catalog: Iterable[str] | None = None,
    ) -> Checkpoint | None:
        """Publish a new Context from exact source snapshots.

        The source recheck and require-new write share one lock set.  This is
        the creation counterpart of ``save_context_with_sources`` and prevents
        both stale locators and a concurrent owner from reaching the new path.
        """
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _ in bindings)
        if (
            not bindings
            or len(source_names) != len(set(source_names))
            or ctx.name in source_names
        ):
            raise ValueError("Invalid Context creation source lock set.")
        _, checkpoints = self._create_contexts_with_ancestors(
            ((ctx, auto_checkpoint),),
            require_all_new=True,
            source_bindings=bindings,
            expected_context_catalog=expected_context_catalog,
        )
        return checkpoints.get(ctx.name)

    def create_branch_context(
        self,
        ctx: Context,
        *,
        source_name: str,
        expected_source_uid: str,
        expected_history_digest: str,
        expected_current: str | None,
    ) -> None:
        """Create, inherit history, and select one exact branch atomically."""
        source = self.load_direct(source_name)
        source_memories = tuple(
            item for item in source.iter_memories() if isinstance(item, Memory)
        )
        target_memories = tuple(
            item for item in ctx.iter_memories() if isinstance(item, Memory)
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
        validate_context_name(source_root)
        validate_context_name(target_root)
        if source_root == target_root:
            raise ValueError("A Branch must have a new Context root name.")

        source_names = tuple(binding.source_name for binding in records)
        target_names = tuple(binding.target.name for binding in records)
        for target_name in target_names:
            validate_context_name(target_name)
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
                for item in binding.target.iter_memories()
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

        source_receipts = tuple(
            (
                binding.source_name,
                binding.expected_source_uid,
            )
            for binding in records
        )
        lock_names = (*source_names, *target_names)
        # Subtree membership is itself part of the reviewed request. An
        # exclusive graph lock prevents a new lexical descendant from
        # appearing after the final membership recheck.
        with self._context_graph_lock(exclusive=True):
            catalog = tuple(self.list_context_names())
            creation_entries = prepare_context_creation_entries(
                (
                    (
                        binding.target,
                        AutoCheckpointRequest(
                            command="branch",
                            command_details={
                                "branch_tree": branch_tree,
                                "command_contexts": command_contexts,
                                "memory_lineage": branch_memory_lineage,
                            },
                        ),
                    )
                    for binding in records
                ),
                catalog,
                current_before=expected_current,
                current_after=target_root,
            )
            implicit_parents = tuple(
                (context, request)
                for context, request in creation_entries
                if context.name not in target_names
            )
            creation_requests = {
                context.name: request for context, request in creation_entries
            }
            validate_context_hierarchy(
                (*catalog, *(context.name for context, _ in creation_entries))
            )
            lock_names = (
                *lock_names,
                *(context.name for context, _ in implicit_parents),
            )
            with self._context_write_locks(lock_names):
                if include_descendants:
                    from memcommit.persistence.store.lookup.context_names import (
                        list_context_and_descendant_names,
                    )

                    live_source_names = list_context_and_descendant_names(
                        (source_root,),
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
                        for item in live_source.iter_memories()
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
                                        object_pairs_hook=(_reject_duplicate_json_keys),
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
                            validate_checkpoint_context_frames(raw)
                            rewritten = raw
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
                        for parent, request in implicit_parents:
                            self._save_locked(parent, request, require_new=True)
                            created.append(parent)
                        for binding in records:
                            target = binding.target
                            self._save_locked(
                                target,
                                None,
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
                                creation_requests[target.name],
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Branch creation recorded no command checkpoint."
                                )
                        state["current"] = target_root
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

    def create_missing_contexts(
        self,
        entries: Iterable[tuple[Context, Optional[AutoCheckpointRequest]]],
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
        created, _ = self._create_contexts_with_ancestors(
            entries,
            make_current=make_current,
            require_all_new=require_all_new,
            expected_current=expected_current,
        )
        return created

    def _create_contexts_with_ancestors(
        self,
        entries,
        *,
        make_current=None,
        require_all_new=False,
        expected_current=_NO_CURRENT_CONTEXT_EXPECTATION,
        source_bindings=(),
        expected_context_catalog=None,
    ):
        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context is required.")
        requested_names = tuple(context.name for context, _ in records)
        for name in requested_names:
            validate_context_name(name)
        if len(requested_names) != len(set(requested_names)):
            raise ValueError("Context batch contains duplicate names.")
        if make_current is not None and make_current not in requested_names:
            raise ValueError("Selected Context must be part of the creation batch.")
        bindings = tuple(source_bindings)
        with self._context_graph_lock(exclusive=True):
            catalog = tuple(self.list_context_names())
            if expected_context_catalog is not None and catalog != tuple(
                expected_context_catalog
            ):
                raise ConcurrentContextUpdateError(
                    "Context namespace changed before creation."
                )
            existing = set(catalog)
            collisions = existing.intersection(requested_names)
            if require_all_new and collisions:
                raise FileExistsError(
                    "Context destination already exists: "
                    + ", ".join(sorted(collisions))
                )
            current_before = self.current_context_name()
            records = prepare_context_creation_entries(
                records,
                existing,
                current_before=current_before,
                current_after=make_current
                if make_current is not None
                else current_before,
            )
            names = tuple(context.name for context, _ in records)
            validate_context_hierarchy((*catalog, *names))
            with self._context_write_locks((*names, *(name for name, _ in bindings))):
                self._assert_source_bindings_locked(bindings)
                for name in names:
                    if name in existing:
                        self.load_direct(name)
                    else:
                        self._assert_context_storage_available(name)
                created = []
                checkpoints = {}
                original_state = None
                try:
                    for context, request in sorted(
                        records, key=lambda entry: entry[0].name.count("/")
                    ):
                        if context.name in existing:
                            continue
                        checkpoint = self._save_locked(
                            context, request, require_new=True
                        )
                        created.append(context)
                        if checkpoint is not None:
                            checkpoints[context.name] = checkpoint
                    if make_current is not None:
                        with self._state_write_lock():
                            state = self._read_state()
                            original_state = dict(state)
                            if (
                                expected_current is not _NO_CURRENT_CONTEXT_EXPECTATION
                                and state.get("current") != expected_current
                            ):
                                raise ConcurrentContextUpdateError(
                                    "The current Context changed before creation."
                                )
                            state["current"] = make_current
                            self._write_state(state)
                except Exception:
                    rollback_error = None
                    if original_state is not None:
                        try:
                            with self._state_write_lock():
                                _write_json_atomic(self.state_file, original_state)
                        except Exception as error:
                            rollback_error = error
                    for context in reversed(created):
                        try:
                            self._delete_locked(context.name, clear_current=False)
                        except Exception as error:
                            rollback_error = rollback_error or error
                    if rollback_error is not None:
                        raise RuntimeError(
                            "Context creation could not be fully rolled back."
                        ) from rollback_error
                    raise
        return tuple(created), checkpoints
