"""Turn one semantic operation result into durable Memories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import memcommit.application.capabilities.ops as ops
from memcommit.core.context import AutoCheckpoint
from memcommit.application.capabilities.context_locator import resolve_context_locator
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


def resolve_semantic_result_endpoints(
    *,
    source_locator: str | None,
    target_locator: str | None,
    current: str | None,
) -> SemanticResultEndpoints:
    """Fill either omitted endpoint from the same frozen Current value.

    Source and Target may intentionally be the same Context. The caller must
    freeze the Source pre-image before inference so generated Memories never
    become input to the provider turn that created them.
    """

    if source_locator is None:
        if current is None:
            raise ValueError("No current Source Context.")
        source_name = current
    else:
        source_name = resolve_context_locator(source_locator, current=current)

    if target_locator is None:
        if current is None:
            raise ValueError("No current Target Context.")
        target_name = current
    else:
        target_name = resolve_context_locator(target_locator, current=current)

    return SemanticResultEndpoints(source_name=source_name, target_name=target_name)


def resolve_memorization_target(
    *,
    target_locator: str | None,
    current: str | None,
) -> str:
    """Resolve an inline-input operation's existing Target."""

    if target_locator is None:
        if current is None:
            raise ValueError("No current Target Context.")
        return current
    return resolve_context_locator(target_locator, current=current)


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
    "resolve_memorization_target",
    "resolve_semantic_result_endpoints",
]
