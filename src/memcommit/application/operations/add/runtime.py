"""MemoryStore infrastructure adapter for Add."""

from __future__ import annotations


from memcommit.models.memory import Memory
from memcommit.application.operations.add.application import (
    AddedMemory,
    AddRequest,
    AddResult,
    AddTargetPort,
    FrozenAddTarget,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store import ConcurrentContextUpdateError


class _StoreAddTargetToken:
    def __init__(self, access):
        self.access = access


def _checkpoint_command_details(
    request: AddRequest,
    *,
    memory_uids: list[str],
) -> dict[str, object]:
    contents = list(request.contents)
    return {
        "count": len(contents),
        "contents": contents,
        "memory_uids": memory_uids,
    }




class MemoryStoreAddTargetPort(AddTargetPort):
    """Commit Add against one current-Context snapshot and exact target CAS."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        current_context_name: str | None,
    ):
        self._store = store
        # Relative target meaning must not drift if another process switches
        # the global current Context while this request is being composed.
        self._current_context_name = current_context_name

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreAddTargetPort":
        return cls(
            store,
            current_context_name=store.current_context_name(),
        )

    def freeze(self, context_locator: str | None) -> FrozenAddTarget:
        access = resolve_existing_context_access(
            self._store,
            context_locator,
            current_name=self._current_context_name,
        ).value
        context = access.store.load_direct(access.context_name)
        return FrozenAddTarget(
            context_name=access.access_name,
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
        store = access.store
        context = store.load_direct(access.context_name)
        if context.uid != target.context_uid:
            raise ConcurrentContextUpdateError(
                f"Context '{target.context_name}' was replaced while "
                "Add was open; "
                "no changes were made."
            )
        memories = [context.add(Memory.create(content)) for content in request.contents]
        checkpoint = store.save(
            context,
            AutoCheckpointRequest(
                command="add",
                command_details=_checkpoint_command_details(
                    request,
                    memory_uids=[memory.uid for memory in memories],
                ),
            ),
        )
        if checkpoint is None:
            raise RuntimeError("Add saved no checkpoint.")
        return AddResult(
            context_name=access.access_name,
            context_uid=context.uid,
            memories=tuple(
                AddedMemory(uid=memory.uid, content=memory.content)
                for memory in memories
            ),
            checkpoint_uid=checkpoint.uid,
        )
