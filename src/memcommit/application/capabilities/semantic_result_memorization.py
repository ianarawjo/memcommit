"""Turn one semantic operation result into durable Memories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import memcommit.application.capabilities.ops as ops
from memcommit.core.context import AutoCheckpoint
from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class SemanticResultEndpoints:
    """Canonical Source and Target names resolved from one Current snapshot."""

    source_name: str
    target_name: str


@dataclass(frozen=True)
class FrozenMemorizationTarget:
    """One existing local Target frozen before semantic inference begins."""

    context_name: str
    context_uid: str
    context_digest: str


@dataclass(frozen=True)
class SemanticResultMemorizationReceipt:
    """Complete receipt for one atomic semantic-result memorization."""

    operation: str
    source_name: str | None
    target_name: str
    target_uid: str
    memory_uids: tuple[str, ...]
    checkpoint_uid: str

    @property
    def count(self) -> int:
        return len(self.memory_uids)


def resolve_existing_semantic_result_endpoints(
    store: MemoryStore,
    *,
    source_locator: str | None,
    target_locator: str | None,
    current: str | None,
) -> SemanticResultEndpoints:
    """Resolve one readable Source and one existing ordinary-local Target.

    The Source may be a READ-granted public Context. The memorization Target
    stays ordinary-local because this capability freezes and later mutates its
    record directly. Both operands share one command-start current snapshot,
    while their candidate catalogs remain separate authority namespaces.
    """

    if source_locator is None and current is None:
        raise ValueError("No current Source Context.")
    if target_locator is None and current is None:
        raise ValueError("No current Target Context.")
    source_candidates = freeze_profile_context_access_candidates(
        store,
        current_name=current,
    )
    source = resolve_existing_context_access(
        store,
        source_locator if source_locator is not None else current,
        current_name=current,
        required_permission="READ",
        candidates=source_candidates,
    )
    target = resolve_existing_context_operand(
        freeze_local_context_operand_candidates(store),
        target_locator if target_locator is not None else current,
        current=current,
    )
    return SemanticResultEndpoints(
        source_name=source.name,
        target_name=target.name,
    )


def resolve_existing_memorization_target(
    store: MemoryStore,
    *,
    target_locator: str | None,
    current: str | None,
) -> str:
    """Resolve an inline-input operation's existing ordinary-local Target."""

    if target_locator is None and current is None:
        raise ValueError("No current Target Context.")
    return resolve_existing_context_operand(
        freeze_local_context_operand_candidates(store),
        target_locator if target_locator is not None else current,
        current=current,
    ).name


def freeze_memorization_target(
    store: MemoryStore,
    context_name: str,
) -> FrozenMemorizationTarget:
    """Freeze one existing local Target before provider construction."""

    if not store.context_exists(context_name):
        raise FileNotFoundError(f"Context {context_name!r} not found.")
    context = store.load_direct(context_name)
    return FrozenMemorizationTarget(
        context_name=context.name,
        context_uid=context.uid,
        context_digest=context_record_digest(context),
    )


def memorize_semantic_result(
    *,
    store: MemoryStore,
    operation: str,
    source_name: str | None,
    target: FrozenMemorizationTarget,
    contents: tuple[str, ...],
    source_bindings: Iterable[tuple[str, str, str]],
    operation_args: dict[str, object],
    description: str,
) -> SemanticResultMemorizationReceipt:
    """Memorize every result item or publish none of them.

    A separate Source remains locked and exact through the Target write. When
    Source and Target are the same, Target CAS protects the consumed pre-image
    and the duplicate Source binding is deliberately omitted.
    """

    if not operation or not contents or any(not value.strip() for value in contents):
        raise ValueError(
            "Semantic result memorization requires nonblank Memory contents."
        )
    current = store.load_direct(target.context_name)
    if (
        current.uid != target.context_uid
        or context_record_digest(current) != target.context_digest
    ):
        raise RuntimeError(
            f"Target Context '{target.context_name}' changed while {operation.title()} "
            "was running; no generated Memories were added."
        )

    memories = ops.add_many(current, list(contents))
    bindings = tuple(
        binding
        for binding in source_bindings
        if binding[0] != target.context_name
    )
    checkpoint_args = {
        operation: {
            **operation_args,
            "effect": "ADD",
            "source_context": source_name,
            "target_context": target.context_name,
            "result_memory_uids": [memory.uid for memory in memories],
        }
    }
    checkpoint_request = AutoCheckpoint(
        command=operation,
        args=checkpoint_args,
        description=description,
    )
    if bindings:
        checkpoint = store.save_context_with_sources(
            current,
            checkpoint_request,
            expected_context_digest=target.context_digest,
            source_bindings=bindings,
        )
    else:
        checkpoint = store.save(
            current,
            checkpoint_request,
            expected_context_digest=target.context_digest,
        )
    if checkpoint is None:
        raise RuntimeError(
            f"{operation.title()} result memorization created no checkpoint."
        )
    return SemanticResultMemorizationReceipt(
        operation=operation,
        source_name=source_name,
        target_name=target.context_name,
        target_uid=target.context_uid,
        memory_uids=tuple(memory.uid for memory in memories),
        checkpoint_uid=checkpoint.uid,
    )


__all__ = [
    "FrozenMemorizationTarget",
    "SemanticResultEndpoints",
    "SemanticResultMemorizationReceipt",
    "freeze_memorization_target",
    "memorize_semantic_result",
    "resolve_existing_memorization_target",
    "resolve_existing_semantic_result_endpoints",
]
