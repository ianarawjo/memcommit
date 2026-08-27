"""MemoryStore composition for exact and lexical-subtree Branch."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.application.ops as ops
from memcommit.context import Memory
from memcommit.application.retained_history.memory_lineage import memory_content_sha256
from memcommit.application.operations.branch.application import (
    BranchError,
    BranchPlan,
    BranchRequest,
    BranchResult,
    BranchedContext,
    run_branch,
)
from memcommit.persistence.store import (
    ContextBranchBinding,
    ContextBranchMemoryBinding,
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
)


@dataclass(frozen=True, slots=True)
class BranchSetupSnapshot:
    """Current pointer and local namespace frozen once at command start."""

    expected_current: str | None
    local_context_names: tuple[str, ...]


def prepare_branch(store: MemoryStore) -> BranchSetupSnapshot:
    """Capture all state that determines interactive and relative Branch input."""

    return BranchSetupSnapshot(
        expected_current=store.current_context_name(),
        local_context_names=tuple(store.list_context_names()),
    )


class MemoryStoreBranchPort:
    """Build fresh identities and publish a Branch through the Store CAS."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def apply(self, plan: BranchPlan) -> BranchResult:
        request = plan.request
        if self._store.context_exists(request.target_name):
            raise FileExistsError(
                f"Context '{request.target_name}' already exists."
            )

        sources = tuple(
            self._store.load_for_update(context.source_name)
            for context in plan.contexts
        )
        histories = {
            source.name: self._store.list_checkpoints(source.name)
            for source in sources
        }
        targets = (
            ops.branch_subtree(
                sources,
                request.source_name,
                request.target_name,
            )
            if request.include_descendants
            else (ops.branch(sources[0], request.target_name),)
        )
        if tuple(target.name for target in targets) != tuple(
            context.target_name for context in plan.contexts
        ):
            raise BranchError("Branch materialization escaped its planned mapping.")

        bindings = tuple(
            ContextBranchBinding(
                source_name=source.name,
                expected_source_uid=source.uid,
                expected_source_digest=context_record_digest(source),
                expected_history_digest=checkpoint_history_digest(
                    histories[source.name]
                ),
                target=target,
                memories=tuple(
                    ContextBranchMemoryBinding(
                        source_uid=source_memory.uid,
                        target_uid=target_memory.uid,
                        source_content_sha256=memory_content_sha256(
                            source_memory.content
                        ),
                        target_content_sha256=memory_content_sha256(
                            target_memory.content
                        ),
                    )
                    for source_memory, target_memory in zip(
                        (
                            item
                            for item in source.iter_items()
                            if isinstance(item, Memory)
                        ),
                        (
                            item
                            for item in target.iter_items()
                            if isinstance(item, Memory)
                        ),
                        strict=True,
                    )
                ),
            )
            for source, target in zip(sources, targets, strict=True)
        )
        self._store.create_branch_contexts(
            bindings,
            source_root=request.source_name,
            target_root=request.target_name,
            include_descendants=request.include_descendants,
            expected_current=request.expected_current,
        )
        return BranchResult(
            source_root=request.source_name,
            target_root=request.target_name,
            include_descendants=request.include_descendants,
            contexts=tuple(
                BranchedContext(
                    source_name=source.name,
                    source_uid=source.uid,
                    target_name=target.name,
                    target_uid=target.uid,
                )
                for source, target in zip(sources, targets, strict=True)
            ),
            current_context_name=request.target_name,
        )


def execute_branch(
    request: BranchRequest,
    *,
    store: MemoryStore,
) -> BranchResult:
    """Execute one Branch against an explicit Store without terminal output."""

    return run_branch(
        request,
        port=MemoryStoreBranchPort(store),
    )


__all__ = [
    "BranchSetupSnapshot",
    "MemoryStoreBranchPort",
    "execute_branch",
    "prepare_branch",
]
