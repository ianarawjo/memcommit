"""MemoryStore infrastructure adapter for immutable Memory References."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint, Memory
from memcommit.context_locator import resolve_context_locator
from memcommit.reference_application import (
    FrozenReferencePlan,
    ReferenceError,
    ReferencePort,
    ReferenceRequest,
    ReferenceResult,
    run_reference,
    validate_reference_request,
)
from memcommit.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class _LocalReferenceToken:
    owner: object


class MemoryStoreReferencePort(ReferencePort):
    """Freeze and publish one local Source snapshot into one local Target."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreReferencePort":
        return cls(store, current_name=store.current_context_name())

    def _canonical(self, locator: str) -> str:
        return resolve_context_locator(locator, current=self._current_name)

    def freeze(self, request: ReferenceRequest) -> FrozenReferencePlan:
        request = validate_reference_request(request)
        source_name = self._canonical(request.source_locator)
        target_locator = request.into_locator or self._current_name
        if target_locator is None:
            raise ReferenceError(
                "No current Context. Pass --into or initialize a Context first."
            )
        into_name = self._canonical(target_locator)
        for name in (source_name, into_name):
            if not self._store.context_exists(name):
                raise FileNotFoundError(f"Context '{name}' does not exist.")
        source = self._store.load_direct(source_name)
        target = self._store.load_for_update(into_name)
        item = ops.resolve(source, request.memory_selector)
        if not isinstance(item, Memory):
            raise TypeError(
                f"'{request.memory_selector}' is not a directly owned Memory "
                f"in '{source_name}'."
            )
        return FrozenReferencePlan(
            request=request,
            source_name=source_name,
            source_uid=source.uid,
            source_digest=context_record_digest(source),
            memory_uid=item.uid,
            memory_content=item.content,
            memory_content_sha256=hashlib.sha256(
                item.content.encode("utf-8")
            ).hexdigest(),
            into_name=into_name,
            into_uid=target.uid,
            into_digest=context_record_digest(target),
            token=_LocalReferenceToken(self._owner),
        )

    def apply(self, plan: FrozenReferencePlan) -> ReferenceResult:
        token = plan.token
        if not isinstance(token, _LocalReferenceToken) or token.owner is not self._owner:
            raise ValueError("The frozen Reference plan belongs to another runtime.")
        source = self._store.load_direct(plan.source_name)
        target = self._store.load_for_update(plan.into_name)
        if (
            source.uid != plan.source_uid
            or context_record_digest(source) != plan.source_digest
        ):
            raise RuntimeError(
                "The Source Context changed after the Reference was frozen."
            )
        if (
            target.uid != plan.into_uid
            or context_record_digest(target) != plan.into_digest
        ):
            raise RuntimeError(
                "The Target Context changed after the Reference was frozen."
            )
        item = source.memories.get(plan.memory_uid)
        if not isinstance(item, Memory):
            raise RuntimeError("The frozen Source Memory is no longer available.")
        digest = hashlib.sha256(item.content.encode("utf-8")).hexdigest()
        if item.content != plan.memory_content or digest != plan.memory_content_sha256:
            raise RuntimeError(
                "The Source Memory changed after the Reference was frozen."
            )
        reference = ops.reference_memory(item, source, target)
        checkpoint = self._store.save_context_with_sources(
            target,
            AutoCheckpoint(
                command="reference",
                args={
                    "reference_uid": reference.uid,
                    "source": plan.source_name,
                    "source_uid": plan.source_uid,
                    "memory_uid": plan.memory_uid,
                    "memory_content_sha256": plan.memory_content_sha256,
                    "into": plan.into_name,
                    "snapshot": True,
                },
                description=(
                    f"Referenced snapshot [{plan.memory_uid[:8]}] from "
                    f"'{plan.source_name}' as [{reference.uid[:8]}] in "
                    f"'{plan.into_name}'"
                ),
            ),
            expected_context_digest=plan.into_digest,
            source_bindings=(
                (plan.source_name, plan.source_uid, plan.source_digest),
            ),
        )
        if checkpoint is None:
            raise RuntimeError("Reference saved no checkpoint.")
        return ReferenceResult(
            reference_uid=reference.uid,
            source_name=plan.source_name,
            source_uid=plan.source_uid,
            memory_uid=plan.memory_uid,
            memory_content_sha256=plan.memory_content_sha256,
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            checkpoint_uid=checkpoint.uid,
        )


def execute_reference(
    request: ReferenceRequest,
    *,
    store: MemoryStore,
) -> ReferenceResult:
    """Execute one local snapshot Reference with no terminal dependency."""

    port = MemoryStoreReferencePort.capture(store)
    return run_reference(request, port=port)


__all__ = ["MemoryStoreReferencePort", "execute_reference"]
