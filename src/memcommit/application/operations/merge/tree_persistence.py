"""Atomic MemoryStore publication for one recursive structural Merge."""

from __future__ import annotations

import json
from dataclasses import dataclass

from memcommit.context import AutoCheckpoint, Checkpoint, Context
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    _write_bytes_atomic,
    context_record_digest,
)


@dataclass(frozen=True)
class MergeTreeWrite:
    """One existing replacement or require-new Context in a tree transaction."""

    context: Context
    expected_uid: str
    expected_digest: str | None
    checkpoint: AutoCheckpoint

    @property
    def require_new(self) -> bool:
        return self.expected_digest is None


def _membership(
    root: str,
    names: tuple[str, ...],
) -> tuple[str, ...]:
    return expand_lexical_context_names(
        ContextScope.create((root,), include_descendants=True),
        names,
    )


def _remove_checkpoint(
    store: MemoryStore,
    name: str,
    checkpoint: Checkpoint,
) -> None:
    for path in store._checkpoints_dir(
        name
    ).glob(  # noqa: SLF001
        f"*-{checkpoint.uid[:8]}.json"
    ):
        if path.is_symlink() or not path.is_file():
            continue
        with open(path, encoding="utf-8") as file:
            value = json.load(file)
        if value.get("uid") == checkpoint.uid:
            path.unlink()
            return
    raise RuntimeError("Recursive Merge rollback lost a checkpoint.")


def commit_merge_tree(
    store: MemoryStore,
    writes: tuple[MergeTreeWrite, ...],
    *,
    source_bindings: tuple[tuple[str, str, str], ...],
    source_root: str | None,
    expected_source_names: tuple[str, ...],
    target_root: str,
    expected_target_names: tuple[str, ...],
) -> tuple[Checkpoint, ...]:
    """Publish every planned Context or restore every pre-transaction byte."""

    if not writes:
        raise ValueError("Recursive Merge requires at least one Target write.")
    target_names = tuple(write.context.name for write in writes)
    source_names = tuple(name for name, _, _ in source_bindings)
    if len(target_names) != len(set(target_names)):
        raise ValueError("Recursive Merge Target writes must be distinct.")
    if len(source_names) != len(set(source_names)):
        raise ValueError("Recursive Merge Source bindings must be distinct.")
    if set(target_names) & set(source_names):
        raise ValueError("Recursive Merge Source and Target trees must not overlap.")

    lock_names = tuple(dict.fromkeys((*source_names, *target_names)))
    with store._command_write_lock():  # noqa: SLF001
        # Membership is part of the reviewed meaning, so creation, deletion,
        # and rename stay excluded through validation, publication, and rollback.
        with store._context_graph_lock(exclusive=True):  # noqa: SLF001
            with store._context_write_locks(lock_names):  # noqa: SLF001
                live_names = tuple(store.list_context_names())
                if (
                    source_root is not None
                    and _membership(
                        source_root,
                        live_names,
                    )
                    != expected_source_names
                ):
                    raise ConcurrentContextUpdateError(
                        "The Source Context subtree changed before the recursive "
                        "Merge could be saved."
                    )
                if _membership(target_root, live_names) != expected_target_names:
                    raise ConcurrentContextUpdateError(
                        "The Target Context subtree changed before the recursive "
                        "Merge could be saved."
                    )
                if source_bindings:
                    store._assert_source_bindings_locked(  # noqa: SLF001
                        source_bindings,
                        result_label="recursive merge",
                    )

                original_bytes: dict[str, bytes] = {}
                for write in writes:
                    name = write.context.name
                    if write.require_new:
                        if store.context_exists(name):
                            store.load_direct(name)
                            raise ConcurrentContextUpdateError(
                                f"Recursive Merge target '{name}' already exists."
                            )
                        store._assert_context_storage_available(name)  # noqa: SLF001
                        continue
                    current = store.load_direct(name)
                    if (
                        current.uid != write.expected_uid
                        or context_record_digest(current) != write.expected_digest
                    ):
                        raise ConcurrentContextUpdateError(
                            f"Recursive Merge target '{name}' changed before save."
                        )
                    store._assert_context_record_change_allowed(  # noqa: SLF001
                        current.to_dict(),
                        write.context,
                    )
                    original_bytes[name] = store._context_file(  # noqa: SLF001
                        name
                    ).read_bytes()

                saved: list[tuple[MergeTreeWrite, Checkpoint]] = []
                created: list[MergeTreeWrite] = []
                try:
                    for write in writes:
                        checkpoint = store._save_locked(  # noqa: SLF001
                            write.context,
                            write.checkpoint,
                            expected_context_digest=write.expected_digest,
                            require_new=write.require_new,
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Recursive Merge saved no Context checkpoint."
                            )
                        saved.append((write, checkpoint))
                        if write.require_new:
                            created.append(write)
                except Exception:
                    rollback_error: Exception | None = None
                    created_names = {write.context.name for write in created}
                    for write in reversed(created):
                        try:
                            store._delete_locked(write.context.name)  # noqa: SLF001
                        except Exception as candidate:
                            rollback_error = rollback_error or candidate
                    for write, checkpoint in reversed(saved):
                        name = write.context.name
                        if name in created_names:
                            continue
                        try:
                            _write_bytes_atomic(
                                store._context_file(name),  # noqa: SLF001
                                original_bytes[name],
                            )
                            _remove_checkpoint(store, name, checkpoint)
                        except Exception as candidate:
                            rollback_error = rollback_error or candidate
                    if rollback_error is not None:
                        raise RuntimeError(
                            "Recursive Merge failed and its Context tree could "
                            "not be fully rolled back."
                        ) from rollback_error
                    raise
    for write in writes:
        write.context._store_digest = context_record_digest(write.context)
    return tuple(checkpoint for _, checkpoint in saved)
