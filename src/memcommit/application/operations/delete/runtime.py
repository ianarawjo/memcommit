"""Store and checkpoint adapter for Delete."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.core.context_targeting.direct_items as direct_items
from memcommit.application.context_access.access import ContextAccess
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.operations.delete.application import (
    ContextDeletePlan,
    ContextDeleteResult,
    MemDeleteError,
    DeletePort,
    DeletedDirectItem,
    DirectItemDeleteRequest,
    DirectItemDeleteResult,
    FrozenDirectItemDeleteTarget,
    run_direct_item_delete,
)
from memcommit.persistence.store import ContextDeletionCommittedError, ProfileStore
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)


def prepare_current_context_delete(store: ProfileStore) -> ContextDeletePlan:
    current_name = store.current_context_name()
    if current_name is None:
        raise MemDeleteError(
            "No current Context. Run 'mem switch' or 'mem init' first."
        )
    names = list_context_and_descendant_names(
        (current_name,), store.list_context_names()
    )
    contexts = tuple(store.load_direct(name) for name in names)
    return ContextDeletePlan(
        context_name=current_name,
        context_identities=tuple((context.name, context.uid) for context in contexts),
    )


def apply_context_delete(
    plan: ContextDeletePlan,
    *,
    store: ProfileStore,
) -> ContextDeleteResult:
    try:
        store.delete_context_and_descendants(
            plan.context_name,
            expected_contexts=plan.context_identities,
            expected_current=plan.context_name,
        )
    except ContextDeletionCommittedError as error:
        return ContextDeleteResult(
            plan.context_name,
            len(plan.context_identities),
            cleanup_warning=str(error),
        )
    return ContextDeleteResult(plan.context_name, len(plan.context_identities))


@dataclass(frozen=True, slots=True)
class _ItemToken:
    owner: object
    access: ContextAccess
    context: Context
    item: Memory


def _project_item(item: Memory) -> DeletedDirectItem:
    if isinstance(item, Memory):
        return DeletedDirectItem(kind="MEMORY", uid=item.uid, content=item.content)
    raise TypeError(f"Unsupported direct item type: {type(item).__name__}")


class MemoryStoreDeletePort(DeletePort):
    """Freeze one command-start locator snapshot and execute exact mutations."""

    def __init__(self, store: ProfileStore, *, current_name: str | None) -> None:
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: ProfileStore) -> "MemoryStoreDeletePort":
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
            raise MemDeleteError(
                "No current Context. Run 'mem switch' or 'mem init' first."
            )
        if request.context_locator not in (None, self._current_name):
            raise MemDeleteError(
                "Delete can modify only the current Context; switch first."
            )
        context = self._store.load_direct(self._current_name)
        memory = direct_items.resolve_direct_memory(context, request.selector)
        return self.freeze_loaded_memory(context, memory)

    def freeze_loaded_memory(
        self,
        context: Context,
        memory: Memory,
    ) -> FrozenDirectItemDeleteTarget:
        if context.name != self._current_name:
            raise MemDeleteError(
                "Delete can modify only the current Context; switch first."
            )
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


def execute_direct_item_delete(
    request: DirectItemDeleteRequest,
    *,
    store: ProfileStore,
) -> DirectItemDeleteResult:
    """Execute one direct-item removal without terminal or provider access."""

    return run_direct_item_delete(
        request,
        port=MemoryStoreDeletePort.capture(store),
    )


__all__ = [
    "MemoryStoreDeletePort",
    "execute_direct_item_delete",
    "prepare_current_context_delete",
    "apply_context_delete",
]
