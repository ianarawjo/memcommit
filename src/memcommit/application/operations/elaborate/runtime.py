"""ProfileStore binding for append-only Elaborate preparation and Apply."""

from __future__ import annotations


from dataclasses import dataclass

import memcommit.core.context_targeting.direct_items as direct_items
from memcommit.application.context_access.access import ContextAccess
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
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
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.persistence.store import ProfileStore, context_record_digest


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
            (item for item in context.iter_memories() if isinstance(item, Memory)),
            start=1,
        )
    )
    target_alias = next(
        (source.alias for source in sources if source.memory_uid == memory_uid),
        None,
    )
    if target_alias is None:
        raise ElaborateError(
            "The selected Memory is no longer directly owned by its Context."
        )
    return ElaborateFrame(
        context_uid=context.uid,
        context_name=access.access_name,
        context_digest=context_record_digest(context),
        target_alias=target_alias,
        sources=sources,
    )


class MemoryStoreElaboratePort(ElaborateSourcePort):
    """Freeze one READ+EDIT target and reject drift before Apply."""

    def __init__(self, store: ProfileStore, *, current_name: str | None):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: ProfileStore) -> "MemoryStoreElaboratePort":
        return cls(store, current_name=store.current_context_name())

    def _current_access(self, token: _StoreElaborateToken) -> ContextAccess:
        return token.access

    def freeze(self, request: ElaborateRequest) -> FrozenElaborateSource:
        locator = parse_direct_memory_locator(
            request.memory_selector,
            explicit_context=request.context_locator,
        )
        candidates = freeze_profile_context_access_candidates(
            self._store,
            current_name=self._current_name,
        )
        access = resolve_existing_context_access(
            self._store,
            locator.context_locator,
            current_name=self._current_name,
            candidates=candidates,
        ).value
        context = access.store.load_direct(access.context_name)
        target = direct_items.resolve_direct_memory(context, locator.memory_selector)
        return FrozenElaborateSource(
            frame=_frame_for(access, context, memory_uid=target.uid),
            token=_StoreElaborateToken(self._owner, access),
        )

    def revalidate(self, source: FrozenElaborateSource) -> ElaborateFrame:
        token = source.token
        if (
            not isinstance(token, _StoreElaborateToken)
            or token.owner is not self._owner
        ):
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
        target = direct_items.resolve_direct_memory(context, revision.memory_uid)
        if target.content != revision.original_content:
            raise ElaborateError(
                "The selected Memory changed before Elaborate Apply; "
                "no changes were made."
            )
        context.replace_memory(
            Memory(uid=revision.memory_uid, content=revision.content)
        )
        effect = {
            "kind": "APPEND",
            "memory_uid": revision.memory_uid,
            "before": revision.original_content,
            "after": revision.content,
            "continuation": revision.continuation,
            "reason": revision.reason,
            "source_memory_uids": list(revision.source_memory_uids),
        }
        checkpoint = access.store.save(
            context,
            AutoCheckpointRequest(
                command="elaborate",
                command_details={
                    "contract": "append-only-v1",
                    "memory_uid": revision.memory_uid,
                    "continuation": revision.continuation,
                    "source_memory_uids": list(revision.source_memory_uids),
                    "effects": [effect],
                },
            ),
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
    store: ProfileStore,
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
    store: ProfileStore,
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
