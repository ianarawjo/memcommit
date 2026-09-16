"""MemoryStore and Grant adapter for one complete exact-Memory Edit request."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.core.context_targeting.direct_items as direct_items
from memcommit.application.authorization.context_operation import (
    authorized_context_mutation,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    grant_checkpoint_args,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.application.capabilities.local_target_lookup import (
    resolve_local_direct_memory_locator,
)
from memcommit.application.operations.edit.application import (
    EditBatchRequest,
    EditBatchResult,
    EditMemoryChange,
    EditPort,
    EditRequest,
    EditResult,
    FrozenEditBatchPlan,
    FrozenEditPlan,
    edit_target_selector,
    planned_edits,
    run_edit,
    validate_edit_request,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class _StoreEditToken:
    owner: object
    access: ContextAccess
    request: EditRequest | EditBatchRequest
    context_uid: str
    context_digest: str
    edits: tuple[EditMemoryChange, ...]


class MemoryStoreEditPort(EditPort):
    """Freeze UPDATE authority and every before value before any replacement."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self.store = store
        self.current_context_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> MemoryStoreEditPort:
        return cls(store, current_name=store.current_context_name())

    def access(self, context_locator: str | None) -> ContextAccess:
        return resolve_existing_context_access(
            self.store,
            context_locator,
            current_name=self.current_context_name,
            required_permission="UPDATE",
        ).value

    def inspect_context(self, context_locator: str | None) -> Context:
        access = self.access(context_locator)
        return access.store.load_direct(access.context_name)

    def freeze(
        self,
        request: EditRequest | EditBatchRequest,
    ) -> FrozenEditPlan | FrozenEditBatchPlan:
        validate_edit_request(request)
        if isinstance(request, EditBatchRequest):
            # A batch's selectors belong to one Context, even when it has one row.
            # Never broaden file/stdin input into the single-selector Profile search.
            access = self.access(request.context_locator)
            entries = request.edits
        else:
            target = edit_target_selector(request)
            if target.context_locator is not None:
                access = self.access(target.context_locator)
                selector = target.memory_selector
            else:
                resolved = resolve_local_direct_memory_locator(
                    self.store,
                    target.memory_selector,
                    current=self.current_context_name,
                )
                access = self.access(resolved.context_name)
                selector = resolved.memory_uid
            entries = ((selector, request.content),)

        context = access.store.load_direct(access.context_name)
        edits: list[EditMemoryChange] = []
        seen_uids: set[str] = set()
        for selector, content in entries:
            item = direct_items.resolve_direct_memory(context, selector)
            if item.uid in seen_uids:
                raise ValueError(
                    f"Memory [{item.uid[:8]}] appears more than once in the edit input."
                )
            seen_uids.add(item.uid)
            edits.append(EditMemoryChange(item.uid, item.content, content))
        token = _StoreEditToken(
            self._owner,
            access,
            request,
            context.uid,
            context_record_digest(context),
            tuple(edits),
        )
        identity = dict(
            request=request,
            context_name=access.access_name,
            context_uid=context.uid,
            context_digest=token.context_digest,
            token=token,
        )
        if isinstance(request, EditBatchRequest):
            return FrozenEditBatchPlan(**identity, edits=token.edits)
        edit = edits[0]
        return FrozenEditPlan(
            **identity,
            memory_uid=edit.memory_uid,
            original_content=edit.original_content,
        )

    def apply(
        self,
        plan: FrozenEditPlan | FrozenEditBatchPlan,
    ) -> EditResult | EditBatchResult:
        token = plan.token
        if not isinstance(token, _StoreEditToken) or token.owner is not self._owner:
            raise ValueError("The frozen Edit plan belongs to another runtime.")
        edits = planned_edits(plan)
        access = token.access
        # Bind the complete request, including unchanged rows, to what was frozen.
        # Dataclass reconstruction must not silently retarget an approved edit.
        if (
            plan.request != token.request
            or edits != token.edits
            or plan.context_name != access.access_name
            or plan.context_uid != token.context_uid
            or plan.context_digest != token.context_digest
        ):
            raise ValueError(
                "The frozen Edit plan no longer matches its runtime binding."
            )
        context = access.store.load_direct(access.context_name)
        if (
            context.uid != plan.context_uid
            or context_record_digest(context) != plan.context_digest
        ):
            raise RuntimeError(
                f"Context '{plan.context_name}' changed while Edit was open; "
                "no changes were made."
            )
        for edit in edits:
            item = context.memories.get(edit.memory_uid)
            if not isinstance(item, Memory) or item.content != edit.original_content:
                raise RuntimeError(
                    "The selected Memory changed while Edit was open; no changes were made."
                )
        changes = tuple(edit for edit in edits if edit.changed)
        checkpoint_uid = None
        if changes:
            # All rows are checked before mutation; the Store publishes the complete
            # post-image through its existing CAS and single-checkpoint boundary.
            for edit in changes:
                context.replace_memory(
                    Memory(uid=edit.memory_uid, content=edit.content)
                )
            with authorized_context_mutation(access):
                checkpoint = access.store.save(
                    context,
                    _edit_checkpoint(plan.request, changes, access),
                    expected_context_digest=plan.context_digest,
                )
            if checkpoint is None:
                raise RuntimeError("Edit saved no checkpoint.")
            checkpoint_uid = checkpoint.uid
        if isinstance(plan, FrozenEditBatchPlan):
            return EditBatchResult(
                plan.context_name,
                plan.context_uid,
                edits,
                checkpoint_uid,
            )
        edit = edits[0]
        return EditResult(
            context_name=plan.context_name,
            context_uid=plan.context_uid,
            memory_uid=edit.memory_uid,
            original_content=edit.original_content,
            content=edit.content,
            checkpoint_uid=checkpoint_uid,
        )


def _edit_checkpoint(
    request: EditRequest | EditBatchRequest,
    changes: tuple[EditMemoryChange, ...],
    access: ContextAccess,
) -> AutoCheckpoint:
    if isinstance(request, EditBatchRequest):
        args = {
            "input": request.input_source,
            "mode": "uid-tab-content",
            "count": len(changes),
            "uids": [edit.memory_uid for edit in changes],
            "edits": [
                {"uid": edit.memory_uid, "content": edit.content} for edit in changes
            ],
        }
        description = f"Edited {len(changes)} memories"
        if request.input_source is not None:
            description += f" from {'stdin' if request.input_source == '-' else repr(request.input_source)}"
    else:
        edit = changes[0]
        args = {"uid": edit.memory_uid, "content": edit.content}
        description = f"Edited memory [{edit.memory_uid[:8]}]"
    return AutoCheckpoint(
        command="edit",
        args={**args, **grant_checkpoint_args(access)},
        description=description,
    )


def execute_edit(
    request: EditRequest | EditBatchRequest,
    *,
    store: MemoryStore,
) -> EditResult | EditBatchResult:
    return run_edit(request, port=MemoryStoreEditPort.capture(store))


__all__ = ["MemoryStoreEditPort", "execute_edit"]
