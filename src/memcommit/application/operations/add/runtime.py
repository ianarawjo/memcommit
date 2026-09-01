"""MemoryStore and Grant infrastructure adapter for Add."""

from __future__ import annotations

import memcommit.application.capabilities.ops as ops
from memcommit.application.authorization import ContextUse, authorize_context_use
from memcommit.application.operations.add.application import (
    AddedMemory,
    AddRequest,
    AddResult,
    AddTargetPort,
    FrozenAddTarget,
    run_add,
)
from memcommit.application.authorization.context_operation import (
    authorized_context_mutation,
)
from memcommit.application.context_access.access import (
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.capabilities.operand_resolution import (
    resolve_existing_local_context_operand,
)
from memcommit.core.context import AutoCheckpoint
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store import ConcurrentContextUpdateError


class _StoreAddTargetToken:
    def __init__(self, access):
        self.access = access


def _checkpoint_args(
    request: AddRequest,
    *,
    memory_uids: list[str],
    access,
) -> dict[str, object]:
    contents = list(request.contents)
    return {
        "count": len(contents),
        "contents": contents,
        "memory_uids": memory_uids,
        **grant_checkpoint_args(access),
    }


def _checkpoint_description(request: AddRequest) -> str:
    count = len(request.contents)
    noun = "Memory" if count == 1 else "Memories"
    return f"Added {count} {noun}"


class MemoryStoreAddTargetPort(AddTargetPort):
    """Commit Add against one current-Context snapshot and exact target CAS."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        current_name: str | None,
        local_only: bool = False,
    ):
        self._store = store
        # Relative target meaning must not drift if another process switches
        # the global current Context while this request is being composed.
        self._current_name = current_name
        self._local_only = local_only

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreAddTargetPort":
        return cls(store, current_name=store.current_context_name())

    def freeze(self, context_locator: str | None) -> FrozenAddTarget:
        if self._local_only:
            canonical = resolve_existing_local_context_operand(
                self._store,
                context_locator,
                current=self._current_name,
            ).name
            access = resolve_context_access(
                self._store,
                canonical,
                current_name=self._current_name,
                required_permission="CREATE",
            )
        else:
            access = resolve_existing_context_access(
                self._store,
                context_locator,
                current_name=self._current_name,
                required_permission="CREATE",
            ).value
        authorize_context_use(access, ContextUse.CREATE)
        context = access.store.load_direct(access.context_name)
        return FrozenAddTarget(
            context_name=access.display_name,
            context_uid=context.uid,
            token=_StoreAddTargetToken(access),
        )

    def append(
        self,
        target: FrozenAddTarget,
        request: AddRequest,
    ) -> AddResult:
        token = target.token
        if not isinstance(token, _StoreAddTargetToken):
            raise ValueError("The frozen Add target binding is invalid.")
        access = token.access
        authorize_context_use(access, ContextUse.CREATE)
        store = access.store
        context = store.load_direct(access.context_name)
        if context.uid != target.context_uid:
            raise ConcurrentContextUpdateError(
                f"Context '{target.context_name}' was replaced while "
                "Add was open; "
                "no changes were made."
            )
        memories = ops.add_many(context, list(request.contents))
        with authorized_context_mutation(access):
            checkpoint = store.save(
                context,
                AutoCheckpoint(
                    command="add",
                    args=_checkpoint_args(
                        request,
                        memory_uids=[memory.uid for memory in memories],
                        access=access,
                    ),
                    description=_checkpoint_description(request),
                ),
            )
        if checkpoint is None:
            raise RuntimeError("Add saved no checkpoint.")
        return AddResult(
            context_name=access.display_name,
            context_uid=context.uid,
            memories=tuple(
                AddedMemory(uid=memory.uid, content=memory.content)
                for memory in memories
            ),
            checkpoint_uid=checkpoint.uid,
        )


def execute_add(request: AddRequest, *, store: MemoryStore) -> AddResult:
    """Execute Add against a real Store with no terminal or provider output."""

    return run_add(
        request,
        target_port=MemoryStoreAddTargetPort.capture(store),
    )
