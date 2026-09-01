"""MemoryStore implementation of shared Lock and Unlock mechanics."""

from __future__ import annotations

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.operand_resolution import (
    ResolvedExistingContextOperand,
    resolve_existing_local_context_operand,
)
from memcommit.application.capabilities.write_protection.application import (
    ContextProtectionRequest,
    ProfileProtectionRequest,
    WriteProtectionRequest,
    WriteProtectionResult,
)
from memcommit.core.context import Memory
from memcommit.core.context_targeting.model import ContextTarget
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)


def _context_target(
    store: MemoryStore,
    locator: str | None,
    *,
    current_context_name: str | None,
) -> ResolvedExistingContextOperand[ContextTarget]:
    return resolve_existing_local_context_operand(
        store,
        locator,
        current=current_context_name,
    )


class MemoryStoreWriteProtectionPort:
    """Apply one protection effect against one command-start Store snapshot."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def apply(
        self,
        request: WriteProtectionRequest,
        *,
        protected: bool,
    ) -> WriteProtectionResult:
        if isinstance(request, ProfileProtectionRequest):
            changed = self._store.set_profile_write_protection(protected=protected)
            return WriteProtectionResult(
                target_kind="PROFILE",
                protected=protected,
                changed_count=int(changed),
                total_count=1,
            )

        resolved_context = _context_target(
            self._store,
            request.context_locator,
            current_context_name=request.current_context_name,
        )
        name = resolved_context.name
        context = self._store.load_direct(name)
        if context.uid != resolved_context.uid:
            raise ConcurrentContextUpdateError(
                f"Context {name!r} changed identity during target resolution."
            )
        if isinstance(request, ContextProtectionRequest):
            if request.recursive:
                prefix = name + "/"
                expected_contexts = tuple(
                    (
                        candidate.name,
                        candidate.uid,
                        context_record_digest(candidate),
                    )
                    for candidate in self._store.load_direct_context_graph_strict()
                    if candidate.name == name or candidate.name.startswith(prefix)
                )
                if not any(
                    candidate_name == name
                    for candidate_name, _, _ in expected_contexts
                ):
                    raise FileNotFoundError(f"Context '{name}' not found.")
                total, changed_count = (
                    self._store.set_context_namespace_write_protection(
                        name,
                        expected_contexts,
                        protected=protected,
                    )
                )
                return WriteProtectionResult(
                    target_kind="CONTEXT",
                    protected=protected,
                    changed_count=changed_count,
                    total_count=total,
                    context_name=name,
                    recursive=True,
                )
            changed = self._store.set_context_write_protection(
                name,
                protected=protected,
                expected_context_uid=context.uid,
                expected_context_digest=context_record_digest(context),
            )
            return WriteProtectionResult(
                target_kind="CONTEXT",
                protected=protected,
                changed_count=int(changed),
                total_count=1,
                context_name=name,
            )

        item = ops.resolve(context, request.memory_selector)
        if not isinstance(item, Memory):
            raise TypeError(
                f"'{request.memory_selector}' is not a directly owned Memory "
                f"in Context '{name}'."
            )
        changed = self._store.set_memory_write_protection(
            name,
            item.uid,
            protected=protected,
            expected_context_uid=context.uid,
            expected_context_digest=context_record_digest(context),
        )
        return WriteProtectionResult(
            target_kind="MEMORY",
            protected=protected,
            changed_count=int(changed),
            total_count=1,
            context_name=name,
            memory_uid=item.uid,
        )


__all__ = ["MemoryStoreWriteProtectionPort"]
