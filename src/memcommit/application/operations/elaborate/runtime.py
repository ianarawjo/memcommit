"""MemoryStore binding for append-only Elaborate preparation and Apply."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    authorized_context_mutation,
    freeze_granted_context_binding,
    grant_checkpoint_args,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.authority.source_use_policy import (
    authorize_combination,
)
from memcommit.application.operations.profile.model import (
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.update.model import GrantedUpdateTarget
from memcommit.application.operations.elaborate.application import (
    ElaborateError,
    ElaboratePrepared,
    ElaborateProviderFactory,
    ElaborateRequest,
    ElaborateSourcePort,
    FrozenElaborateSource,
    prepare_elaborate,
)
from memcommit.application.operations.elaborate.model import (
    ElaborateFrame,
    ElaborateSource,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.persistence.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class ElaborateReceipt:
    context_name: str
    context_uid: str
    memory_uid: str
    original_content: str
    continuation: str
    content: str
    reason: str
    source_memory_uids: tuple[str, ...]
    checkpoint_uid: str | None

    @property
    def changed(self) -> bool:
        return self.original_content != self.content


@dataclass(frozen=True)
class _StoreElaborateToken:
    owner: object
    access: ContextAccess
    granted_binding: GrantedUpdateTarget | None


def _frame_for(
    access: ContextAccess,
    context: Context,
    *,
    memory_uid: str,
) -> ElaborateFrame:
    sources = tuple(
        ElaborateSource(
            alias=f"m{index:06d}",
            memory_uid=item.uid,
            content=item.content,
        )
        for index, item in enumerate(
            (
                item
                for item in context.iter_items()
                if isinstance(item, Memory)
            ),
            start=1,
        )
    )
    target_alias = next(
        (
            source.alias
            for source in sources
            if source.memory_uid == memory_uid
        ),
        None,
    )
    if target_alias is None:
        raise ElaborateError(
            "The selected Memory is no longer directly owned by its Context."
        )
    return ElaborateFrame(
        context_uid=context.uid,
        context_name=access.display_name,
        context_digest=context_record_digest(context),
        target_alias=target_alias,
        sources=sources,
    )


class MemoryStoreElaboratePort(ElaborateSourcePort):
    """Freeze one UPDATE+DERIVE target and reject drift before Apply."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreElaboratePort":
        return cls(store, current_name=store.current_context_name())

    def _current_access(self, token: _StoreElaborateToken) -> ContextAccess:
        if token.granted_binding is None:
            return token.access
        with authority_grant_snapshot_lock() as registry:
            access = revalidate_granted_context_binding(
                token.granted_binding,
                required_permission="UPDATE",
                registry=registry,
                active_store=self._store,
            )
            authorize_combination((access,))
            return access

    def freeze(self, request: ElaborateRequest) -> FrozenElaborateSource:
        locator = parse_direct_memory_locator(
            request.memory_selector,
            explicit_context=request.context_locator,
        )
        with authority_grant_snapshot_lock() as registry:
            access = resolve_context_access(
                self._store,
                locator.context_locator,
                current_name=self._current_name,
                required_permission="UPDATE",
                registry=registry,
            )
            # Elaborate combines the target with its ordinary direct-Memory
            # neighbors as read-only support. A granted target therefore needs
            # DERIVE authority before any provider connection is opened.
            authorize_combination((access,))
            context = access.store.load_direct(access.context_name)
            target = ops.resolve_direct_memory(context, locator.memory_selector)
            binding = (
                freeze_granted_context_binding(access)
                if access.is_granted
                else None
            )
        return FrozenElaborateSource(
            frame=_frame_for(access, context, memory_uid=target.uid),
            token=_StoreElaborateToken(self._owner, access, binding),
        )

    def revalidate(self, source: FrozenElaborateSource) -> ElaborateFrame:
        token = source.token
        if not isinstance(token, _StoreElaborateToken) or token.owner is not self._owner:
            raise ValueError("The frozen Elaborate source belongs to another runtime.")
        access = self._current_access(token)
        context = access.store.load_direct(access.context_name)
        return _frame_for(
            access,
            context,
            memory_uid=source.frame.target.memory_uid,
        )

    def apply(self, prepared: ElaboratePrepared) -> ElaborateReceipt:
        if not isinstance(prepared, ElaboratePrepared):
            raise TypeError("Elaborate Apply requires a prepared revision.")
        source = prepared.source
        revision = prepared.revision
        current = self.revalidate(source)
        if current != source.frame:
            raise ElaborateError(
                "The selected Context changed before Elaborate Apply; "
                "no changes were made."
            )
        if not revision.changed:
            return ElaborateReceipt(
                context_name=revision.context_name,
                context_uid=revision.context_uid,
                memory_uid=revision.memory_uid,
                original_content=revision.original_content,
                continuation=revision.continuation,
                content=revision.content,
                reason=revision.reason,
                source_memory_uids=revision.source_memory_uids,
                checkpoint_uid=None,
            )

        token = source.token
        assert isinstance(token, _StoreElaborateToken)
        access = self._current_access(token)
        context = access.store.load_direct(access.context_name)
        if (
            context.uid != revision.context_uid
            or context_record_digest(context) != revision.context_digest
        ):
            raise ElaborateError(
                "The selected Context changed before Elaborate Apply; "
                "no changes were made."
            )
        target = ops.resolve_direct_memory(context, revision.memory_uid)
        if target.content != revision.original_content:
            raise ElaborateError(
                "The selected Memory changed before Elaborate Apply; "
                "no changes were made."
            )
        ops.edit(context, revision.memory_uid, revision.content)
        effect = {
            "kind": "APPEND",
            "memory_uid": revision.memory_uid,
            "before": revision.original_content,
            "after": revision.content,
            "continuation": revision.continuation,
            "reason": revision.reason,
            "source_memory_uids": list(revision.source_memory_uids),
        }
        with authorized_context_mutation(
            access,
            required_permissions=("DERIVE",),
        ):
            checkpoint = access.store.save(
                context,
                AutoCheckpoint(
                    command="elaborate",
                    args={
                        "contract": "append-only-v1",
                        "memory_uid": revision.memory_uid,
                        "continuation": revision.continuation,
                        "source_memory_uids": list(revision.source_memory_uids),
                        "effects": [effect],
                        **grant_checkpoint_args(access),
                    },
                    description=(
                        f"Elaborated memory [{revision.memory_uid[:8]}] by "
                        "appending supported detail"
                    ),
                ),
                expected_context_digest=revision.context_digest,
            )
        if checkpoint is None:
            raise ElaborateError("Elaborate Apply saved no checkpoint.")
        return ElaborateReceipt(
            context_name=revision.context_name,
            context_uid=revision.context_uid,
            memory_uid=revision.memory_uid,
            original_content=revision.original_content,
            continuation=revision.continuation,
            content=revision.content,
            reason=revision.reason,
            source_memory_uids=revision.source_memory_uids,
            checkpoint_uid=checkpoint.uid,
        )


def prepare_elaborate_with_store(
    request: ElaborateRequest,
    *,
    store: MemoryStore,
    provider_factory: ElaborateProviderFactory,
) -> tuple[MemoryStoreElaboratePort, ElaboratePrepared]:
    port = MemoryStoreElaboratePort.capture(store)
    return port, prepare_elaborate(
        request,
        source_port=port,
        provider_factory=provider_factory,
    )


def execute_elaborate(
    request: ElaborateRequest,
    *,
    store: MemoryStore,
    provider_factory: ElaborateProviderFactory,
) -> ElaborateReceipt:
    port, prepared = prepare_elaborate_with_store(
        request,
        store=store,
        provider_factory=provider_factory,
    )
    return port.apply(prepared)


__all__ = [
    "ElaborateReceipt",
    "MemoryStoreElaboratePort",
    "execute_elaborate",
    "prepare_elaborate_with_store",
]
