"""Store and checkpoint adapter for Delete."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.core.context_targeting.direct_items as direct_items
from memcommit.application.context_access.access import ContextAccess
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.operations.delete.application import (
    ContextDeleteRequest,
    ContextDeleteResult,
    MemDeleteError,
    DeletePort,
    DeleteStalePlanError,
    DeletedDirectItem,
    DirectItemDeleteRequest,
    DirectItemDeleteResult,
    FrozenContextDeletePlan,
    FrozenDirectItemDeleteTarget,
    apply_context_delete,
    context_delete_plan_digest,
    prepare_context_delete,
    run_direct_item_delete,
)
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    ContextDeletionCommittedError,
    MemoryStore,
)


@dataclass(frozen=True, slots=True)
class _ItemToken:
    owner: object
    access: ContextAccess
    context: Context
    item: Memory


@dataclass(frozen=True, slots=True)
class _ContextToken:
    owner: object


def _project_item(item: Memory) -> DeletedDirectItem:
    if isinstance(item, Memory):
        return DeletedDirectItem(kind="MEMORY", uid=item.uid, content=item.content)
    raise TypeError(f"Unsupported direct item type: {type(item).__name__}")




class MemoryStoreDeletePort(DeletePort):
    """Freeze one command-start locator snapshot and execute exact mutations."""

    def __init__(self, store: MemoryStore, *, current_name: str | None) -> None:
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreDeletePort":
        try:
            current_name = store.current_context_name()
        except FileNotFoundError:
            current_name = None
        return cls(store, current_name=current_name)

    @property
    def current_name(self) -> str | None:
        return self._current_name

    def freeze_item(
        self,
        request: DirectItemDeleteRequest,
    ) -> FrozenDirectItemDeleteTarget:
        if self._current_name is None:
            raise MemDeleteError("No current Context. Run 'mem switch' or 'mem init' first.")
        if request.context_locator not in (None, self._current_name):
            raise MemDeleteError("Delete can modify only the current Context; switch first.")
        context = self._store.load_direct(self._current_name)
        memory = direct_items.resolve_direct_memory(context, request.selector)
        return self.freeze_loaded_memory(context, memory)

    def freeze_loaded_memory(
        self,
        context: Context,
        memory: Memory,
    ) -> FrozenDirectItemDeleteTarget:
        if context.name != self._current_name:
            raise MemDeleteError("Delete can modify only the current Context; switch first.")
        access = ContextAccess(
            store=self._store,
            context_name=context.name,
            access_name=context.name,
        )
        return FrozenDirectItemDeleteTarget(
            context_name=context.name,
            context_uid=context.uid,
            item=_project_item(memory),
            token=_ItemToken(self._owner, access, context, memory),
        )

    def remove_item(
        self,
        target: FrozenDirectItemDeleteTarget,
    ) -> DirectItemDeleteResult:
        token = target.token
        if not isinstance(token, _ItemToken) or token.owner is not self._owner:
            raise MemDeleteError("Delete item target belongs to a different runtime.")
        if (
            token.context.uid != target.context_uid
            or token.item.uid != target.item.uid
            or _project_item(token.item) != target.item
        ):
            raise MemDeleteError(
                "Delete item target no longer matches its opaque source."
            )
        # The full UID is frozen before mutation so an ambiguous prefix cannot
        # change meaning between selection and the exact-identity deletion.
        removed = token.item
        token.context.remove(removed.uid)
        projected = _project_item(removed)
        checkpoint = token.access.store.save(
            token.context,
            AutoCheckpointRequest(
                command="remove",
                command_details={
                    "uid": projected.uid,
                },
            ),
        )
        if checkpoint is None:
            raise MemDeleteError("Delete item mutation saved no checkpoint.")
        return DirectItemDeleteResult(
            context_name=target.context_name,
            context_uid=target.context_uid,
            item=projected,
            checkpoint_uid=checkpoint.uid,
        )

    def freeze_context(
        self,
        request: ContextDeleteRequest,
    ) -> FrozenContextDeletePlan:
        return self.freeze_exact_context(request.context_locator)

    def freeze_exact_context(self, context_name: str) -> FrozenContextDeletePlan:
        if self._current_name is None:
            raise MemDeleteError("No current Context. Run 'mem switch' or 'mem init' first.")
        if context_name != self._current_name:
            raise MemDeleteError("Delete can remove only the current Context; switch first.")
        context = self._store.load_direct(self._current_name)
        return FrozenContextDeletePlan(
            context_name=context.name,
            context_uid=context.uid,
            plan_digest=context_delete_plan_digest(
                context_name=context.name,
                context_uid=context.uid,
            ),
            token=_ContextToken(self._owner),
        )

    def delete_context(
        self,
        plan: FrozenContextDeletePlan,
    ) -> ContextDeleteResult:
        token = plan.token
        if not isinstance(token, _ContextToken) or token.owner is not self._owner:
            raise MemDeleteError("Delete Context plan belongs to a different runtime.")
        try:
            event = self._store.delete_context_if(
                plan.context_name,
                expected_context_uid=plan.context_uid,
            )
        except ContextDeletionCommittedError as error:
            event = error.event
            return _context_result(
                plan,
                event=event,
                status="APPLIED_WITH_CLEANUP_WARNING",
                cleanup_warning=str(error),
            )
        except ConcurrentContextUpdateError as error:
            raise DeleteStalePlanError(str(error)) from error
        return _context_result(plan, event=event, status="APPLIED")


def _context_result(
    plan: FrozenContextDeletePlan,
    *,
    event,
    status,
    cleanup_warning: str | None = None,
) -> ContextDeleteResult:
    return ContextDeleteResult(
        status=status,
        context_name=plan.context_name,
        context_uid=plan.context_uid,
        plan_digest=plan.plan_digest,
        event_uid=event.event_uid,
        operation_id=event.operation_id,
        previous_checkpoint_status=event.previous_checkpoint_status,
        descendants_preserved=event.descendants_preserved,
        cleanup_warning=cleanup_warning,
    )


def execute_direct_item_delete(
    request: DirectItemDeleteRequest,
    *,
    store: MemoryStore,
) -> DirectItemDeleteResult:
    """Execute one direct-item removal without terminal or provider access."""

    return run_direct_item_delete(
        request,
        port=MemoryStoreDeletePort.capture(store),
    )


def prepare_store_context_delete(
    request: ContextDeleteRequest,
    *,
    store: MemoryStore,
) -> tuple[FrozenContextDeletePlan, MemoryStoreDeletePort]:
    """Prepare one plan and retain the exact runtime that owns its token."""

    port = MemoryStoreDeletePort.capture(store)
    return prepare_context_delete(request, port=port), port


def execute_context_delete(
    plan: FrozenContextDeletePlan,
    *,
    port: MemoryStoreDeletePort,
) -> ContextDeleteResult:
    """Apply a plan through its owning Store runtime."""

    return apply_context_delete(plan, port=port)


__all__ = [
    "MemoryStoreDeletePort",
    "execute_context_delete",
    "execute_direct_item_delete",
    "prepare_store_context_delete",
]
