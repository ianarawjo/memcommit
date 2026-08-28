"""MemoryStore and Grant adapter for exact direct-Memory Edit."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.core.context_targeting.loading import (
    resolve_local_direct_memory_locator,
)
from memcommit.application.operations.edit.application import (
    EditPort,
    EditRequest,
    EditResult,
    FrozenEditPlan,
    edit_target_selector,
    run_edit,
    validate_edit_request,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class _StoreEditToken:
    owner: object
    access: ContextAccess


class MemoryStoreEditPort(EditPort):
    """Freeze UPDATE authority and reject Context drift before one edit."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self.store = store
        self.current_context_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreEditPort":
        return cls(store, current_name=store.current_context_name())

    def access(self, context_locator: str | None) -> ContextAccess:
        return resolve_context_access(
            self.store,
            context_locator,
            current_name=self.current_context_name,
            required_permission="UPDATE",
        )

    def inspect_context(self, context_locator: str | None) -> Context:
        access = self.access(context_locator)
        return access.store.load_direct(access.context_name)

    def _freeze_exact(
        self,
        request: EditRequest,
        *,
        access: ContextAccess,
        context: Context,
        item: Memory,
    ) -> FrozenEditPlan:
        return FrozenEditPlan(
            request=request,
            context_name=access.display_name,
            context_uid=context.uid,
            context_digest=context_record_digest(context),
            memory_uid=item.uid,
            original_content=item.content,
            token=_StoreEditToken(self._owner, access),
        )

    def freeze(self, request: EditRequest) -> FrozenEditPlan:
        request = validate_edit_request(request)
        target = edit_target_selector(request)
        if target.context_locator is not None:
            access = self.access(target.context_locator)
            context = access.store.load_direct(access.context_name)
            item = ops.resolve_direct_memory(context, target.memory_selector)
            return self._freeze_exact(
                request,
                access=access,
                context=context,
                item=item,
            )

        resolved = resolve_local_direct_memory_locator(
            self.store,
            target.memory_selector,
            current=self.current_context_name,
        )
        access = self.access(resolved.context_name)
        context = access.store.load_direct(access.context_name)
        item = ops.resolve_direct_memory(context, resolved.memory_uid)
        return self._freeze_exact(
            request,
            access=access,
            context=context,
            item=item,
        )

    def apply(self, plan: FrozenEditPlan) -> EditResult:
        token = plan.token
        if not isinstance(token, _StoreEditToken) or token.owner is not self._owner:
            raise ValueError("The frozen Edit plan belongs to another runtime.")
        access = token.access
        context = access.store.load_direct(access.context_name)
        if (
            context.uid != plan.context_uid
            or context_record_digest(context) != plan.context_digest
        ):
            raise RuntimeError(
                f"Context '{plan.context_name}' changed while Edit was open; "
                "no changes were made."
            )
        item = context.memories.get(plan.memory_uid)
        if not isinstance(item, Memory) or item.content != plan.original_content:
            raise RuntimeError(
                "The selected Memory changed while Edit was open; no changes were made."
            )
        if item.content == plan.request.content:
            return EditResult(
                context_name=plan.context_name,
                context_uid=plan.context_uid,
                memory_uid=plan.memory_uid,
                original_content=plan.original_content,
                content=plan.request.content,
                checkpoint_uid=None,
            )
        original = ops.edit(context, plan.memory_uid, plan.request.content)
        with authorized_context_mutation(access):
            checkpoint = access.store.save(
                context,
                AutoCheckpoint(
                    command="edit",
                    args={
                        "uid": plan.memory_uid,
                        "content": plan.request.content,
                        **grant_checkpoint_args(access),
                    },
                    description=f"Edited memory [{plan.memory_uid[:8]}]",
                ),
            )
        if checkpoint is None:
            raise RuntimeError("Edit saved no checkpoint.")
        return EditResult(
            context_name=plan.context_name,
            context_uid=plan.context_uid,
            memory_uid=plan.memory_uid,
            original_content=original.content,
            content=plan.request.content,
            checkpoint_uid=checkpoint.uid,
        )


def execute_edit(request: EditRequest, *, store: MemoryStore) -> EditResult:
    return run_edit(request, port=MemoryStoreEditPort.capture(store))


__all__ = ["MemoryStoreEditPort", "execute_edit"]
