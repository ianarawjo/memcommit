"""Store, Profile, Grant, and checkpoint adapter for Delete."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.core.context import AutoCheckpoint, Context, Information, Memory, MemoryRef
from memcommit.core.context import QueryContextRef
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.core.context_targeting.loading import (
    DirectItemNotFoundError,
    resolve_local_direct_item_locator,
)
from memcommit.core.context_targeting.model import DirectItemTarget
from memcommit.application.operations.delete.application import (
    ContextDeleteRequest,
    ContextDeleteResult,
    DeleteError,
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
    context_record_digest,
)


@dataclass(frozen=True, slots=True)
class _ItemToken:
    owner: object
    access: ContextAccess
    context: Context
    item: Information


@dataclass(frozen=True, slots=True)
class _ContextToken:
    owner: object


def _project_item(item: Information) -> DeletedDirectItem:
    if isinstance(item, Memory):
        return DeletedDirectItem(kind="MEMORY", uid=item.uid, content=item.content)
    if isinstance(item, MemoryRef):
        return DeletedDirectItem(
            kind="MEMORY_REF",
            uid=item.uid,
            target_context_name=item.target_context_name,
            target_memory_uid=item.target_memory_uid,
        )
    if isinstance(item, QueryContextRef):
        return DeletedDirectItem(
            kind="QUERY_CONTEXT_REF",
            uid=item.uid,
            name=item.name,
        )
    if isinstance(item, Context):
        return DeletedDirectItem(kind="CONTEXT", uid=item.uid, name=item.name)
    raise TypeError(f"Unsupported direct item type: {type(item).__name__}")


def direct_item_checkpoint_description(item: DeletedDirectItem) -> str:
    """Keep the established human-readable checkpoint meaning terminal-free."""

    if item.kind == "MEMORY":
        assert item.content is not None
        return f'Removed memory [{item.uid[:8]}]: "{item.content[:80]}"'
    if item.kind == "MEMORY_REF":
        assert item.target_context_name is not None
        assert item.target_memory_uid is not None
        return (
            f"Removed Memory Reference [{item.uid[:8]}] to "
            f"'{item.target_context_name}' [{item.target_memory_uid[:8]}]"
        )
    if item.kind == "QUERY_CONTEXT_REF":
        assert item.name is not None
        return f"Removed Query View '{item.name}' [{item.uid[:8]}]"
    assert item.name is not None
    return f"Removed Context '{item.name}' [{item.uid[:8]}] · VIA EMBED"


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
        if request.context_locator is None:
            try:
                target = resolve_local_direct_item_locator(
                    self._store,
                    request.selector,
                    current=self._current_name,
                )
            except DirectItemNotFoundError:
                # Direct Context-like rows can also be addressed by exact name.
                # That grammar is Delete-specific, so retain it only as the
                # current-Context fallback after the shared UID catalog misses.
                pass
            else:
                return self.freeze_local_item_target(target)

        if request.context_locator is not None:
            local_name = resolve_context_locator(
                request.context_locator,
                current=self._current_name,
            )
            if self._store.context_exists(local_name):
                try:
                    target = resolve_local_direct_item_locator(
                        self._store,
                        request.selector,
                        current=self._current_name,
                        explicit_context=request.context_locator,
                    )
                except DirectItemNotFoundError:
                    # Preserve exact embedded/query-view names within an
                    # explicitly qualified local Context.
                    pass
                else:
                    return self.freeze_local_item_target(target)

        access = resolve_context_access(
            self._store,
            request.context_locator,
            current_name=self._current_name,
            required_permission="DELETE",
        )
        context = access.store.load_direct(access.context_name)
        item = ops.resolve(context, request.selector)
        return FrozenDirectItemDeleteTarget(
            context_name=access.display_name,
            context_uid=context.uid,
            item=_project_item(item),
            token=_ItemToken(self._owner, access, context, item),
        )

    def freeze_local_item_target(
        self,
        target: DirectItemTarget,
    ) -> FrozenDirectItemDeleteTarget:
        """Bind one shared exact local coordinate without reinterpreting it."""

        if not isinstance(target, DirectItemTarget):
            raise TypeError("Delete requires an exact direct-item target.")
        context = self._store.load_direct(target.context_name)
        access = ContextAccess(
            store=self._store,
            context_name=target.context_name,
            display_name=target.context_name,
            attachment_name=None,
            permission="DELETE",
        )
        item = ops.resolve(context, target.item_uid)
        return FrozenDirectItemDeleteTarget(
            context_name=target.context_name,
            context_uid=context.uid,
            item=_project_item(item),
            token=_ItemToken(self._owner, access, context, item),
        )

    def remove_item(
        self,
        target: FrozenDirectItemDeleteTarget,
    ) -> DirectItemDeleteResult:
        token = target.token
        if not isinstance(token, _ItemToken) or token.owner is not self._owner:
            raise DeleteError("Delete item target belongs to a different runtime.")
        if (
            token.context.uid != target.context_uid
            or token.item.uid != target.item.uid
            or _project_item(token.item) != target.item
        ):
            raise DeleteError("Delete item target no longer matches its opaque source.")
        # The full UID is frozen before mutation so an ambiguous prefix cannot
        # change meaning between selection and the Store CAS.
        removed = ops.remove(token.context, token.item.uid)
        projected = _project_item(removed)
        with authorized_context_mutation(token.access):
            checkpoint = token.access.store.save(
                token.context,
                AutoCheckpoint(
                    command="remove",
                    args={
                        "uid": projected.uid,
                        **grant_checkpoint_args(token.access),
                    },
                    description=direct_item_checkpoint_description(projected),
                ),
            )
        if checkpoint is None:
            raise DeleteError("Delete item mutation saved no checkpoint.")
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
        canonical = resolve_context_locator(
            request.context_locator,
            current=self._current_name,
        )
        if not self._store.context_exists(canonical):
            raise FileNotFoundError(f"Context '{canonical}' not found.")
        context = self._store.load_direct(canonical)
        digest = context_record_digest(context)
        return FrozenContextDeletePlan(
            context_name=canonical,
            context_uid=context.uid,
            context_digest=digest,
            plan_digest=context_delete_plan_digest(
                context_name=canonical,
                context_uid=context.uid,
                context_digest=digest,
            ),
            token=_ContextToken(self._owner),
        )

    def freeze_exact_context(self, context_name: str) -> FrozenContextDeletePlan:
        """Bind a picker-returned canonical name without locator re-resolution."""

        if not isinstance(context_name, str) or not context_name:
            raise ValueError("Delete picker Context name must be nonblank text.")
        if not self._store.context_exists(context_name):
            raise FileNotFoundError(f"Context '{context_name}' not found.")
        context = self._store.load_direct(context_name)
        digest = context_record_digest(context)
        return FrozenContextDeletePlan(
            context_name=context_name,
            context_uid=context.uid,
            context_digest=digest,
            plan_digest=context_delete_plan_digest(
                context_name=context_name,
                context_uid=context.uid,
                context_digest=digest,
            ),
            token=_ContextToken(self._owner),
        )

    def delete_context(
        self,
        plan: FrozenContextDeletePlan,
    ) -> ContextDeleteResult:
        token = plan.token
        if not isinstance(token, _ContextToken) or token.owner is not self._owner:
            raise DeleteError("Delete Context plan belongs to a different runtime.")
        try:
            event = self._store.delete_context_if(
                plan.context_name,
                expected_context_uid=plan.context_uid,
                expected_context_digest=plan.context_digest,
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
        context_digest=plan.context_digest,
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
    "direct_item_checkpoint_description",
    "execute_context_delete",
    "execute_direct_item_delete",
    "prepare_store_context_delete",
]
