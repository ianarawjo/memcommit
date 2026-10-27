"""ProfileStore adapter for one exact Memory replacement."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.core.context_targeting.direct_items import resolve_direct_memory
from memcommit.application.context_access.access import ContextAccess
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.memory import Memory
from memcommit.application.operations.edit.application import (
    MemEditError,
    EditPort,
    EditRequest,
    EditResult,
    FrozenEditPlan,
    run_edit,
    validate_edit_request,
)
from memcommit.persistence.store import ProfileStore


@dataclass(frozen=True)
class _StoreEditToken:
    owner: object
    access: ContextAccess
    request: EditRequest
    context_uid: str
    memory_uid: str
    original_content: str


class MemoryStoreEditPort(EditPort):
    """Bind one current-Context Memory before replacing its content."""

    def __init__(self, store: ProfileStore, *, current_name: str | None):
        self.store = store
        self.current_context_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: ProfileStore) -> MemoryStoreEditPort:
        return cls(store, current_name=store.current_context_name())

    def access(self, context_locator: str | None) -> ContextAccess:
        if self.current_context_name is None:
            raise MemEditError(
                "No current Context. Run 'mem switch' or 'mem init' first."
            )
        if context_locator not in (None, self.current_context_name):
            raise MemEditError(
                "Edit can modify only the current Context; switch first."
            )
        return ContextAccess(
            store=self.store,
            context_name=self.current_context_name,
            access_name=self.current_context_name,
        )

    def freeze(self, request: EditRequest) -> FrozenEditPlan:
        validate_edit_request(request)
        access = self.access(request.context_locator)
        context = access.store.load_direct(access.context_name)
        memory = resolve_direct_memory(context, request.memory_selector)
        return FrozenEditPlan(
            request=request,
            context_name=access.access_name,
            context_uid=context.uid,
            memory_uid=memory.uid,
            original_content=memory.content,
            token=_StoreEditToken(
                self._owner,
                access,
                request,
                context.uid,
                memory.uid,
                memory.content,
            ),
        )

    def apply(self, plan: FrozenEditPlan) -> EditResult:
        token = plan.token
        if not isinstance(token, _StoreEditToken) or token.owner is not self._owner:
            raise ValueError("The frozen Edit plan belongs to another runtime.")
        access = token.access
        if (
            plan.request != token.request
            or plan.memory_uid != token.memory_uid
            or plan.original_content != token.original_content
            or plan.context_name != access.access_name
            or plan.context_uid != token.context_uid
        ):
            raise ValueError(
                "The frozen Edit plan no longer matches its runtime binding."
            )
        context = access.store.load_direct(access.context_name)
        if context.uid != plan.context_uid:
            raise RuntimeError(
                f"Context '{plan.context_name}' changed while Edit was open; no changes were made."
            )
        memory = context.memories.get(plan.memory_uid)
        if not isinstance(memory, Memory) or memory.content != plan.original_content:
            raise RuntimeError(
                "The selected Memory changed while Edit was open; no changes were made."
            )
        checkpoint_uid = None
        if memory.content != plan.request.content:
            context.replace_memory(Memory(uid=memory.uid, content=plan.request.content))
            checkpoint = access.store.save(
                context,
                AutoCheckpointRequest(
                    command="edit",
                    command_details={
                        "uid": memory.uid,
                        "content": plan.request.content,
                    },
                ),
            )
            if checkpoint is None:
                raise RuntimeError("Edit saved no checkpoint.")
            checkpoint_uid = checkpoint.uid
        return EditResult(
            context_name=plan.context_name,
            context_uid=plan.context_uid,
            memory_uid=plan.memory_uid,
            original_content=plan.original_content,
            content=plan.request.content,
            checkpoint_uid=checkpoint_uid,
        )


def execute_edit(request: EditRequest, *, store: ProfileStore) -> EditResult:
    return run_edit(request, port=MemoryStoreEditPort.capture(store))


__all__ = ["MemoryStoreEditPort", "execute_edit"]
