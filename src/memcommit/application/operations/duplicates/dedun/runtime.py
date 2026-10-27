"""Direct semantic Dedup adapter and shared recursive receipt values."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.context_access.access import (
    ContextAccess,
    resolve_context_access,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.memory import Memory
from memcommit.application.operations.duplicates.dedun.application import (
    DedunConflictError,
    DedunError,
    DedunProjection,
    DedunReceipt,
    DedunRequest,
    FrozenDedunPlan,
    dedun_projection_record,
)
from memcommit.application.operations.duplicates.dedun.analysis import (
    freeze_dedun_analysis,
)
from memcommit.application.operations.review.model import direct_context_digest
from memcommit.persistence.store import ProfileStore, context_record_digest


@dataclass
class MemoryStoreDedunPort:
    """Apply confirmed duplicate components in one exact Context."""

    active_store: ProfileStore
    current_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.active_store, ProfileStore):
            raise TypeError("Dedun runtime requires a ProfileStore.")

    def _access(self, request: DedunRequest) -> ContextAccess:
        source = request.source
        return resolve_context_access(
            self.active_store, source.display_name, current_name=self.current_name
        )

    def freeze(self, request: DedunRequest) -> FrozenDedunPlan:
        if not isinstance(request, DedunRequest):
            raise TypeError("Dedun freeze requires a typed request.")
        access = self._access(request)
        source = request.source
        context = access.store.load_direct(access.context_name)
        if (
            context.uid != source.context_uid
            or access.access_name != source.display_name
        ):
            raise DedunConflictError(
                "The confirmed duplicate Source identity changed. Run the finder again."
            )
        if direct_context_digest(context) != source.direct_memory_digest:
            raise DedunConflictError(
                "The confirmed duplicate Source changed. Run the finder again."
            )
        memories = tuple(
            (item for item in context.iter_memories() if isinstance(item, Memory))
        )
        digest = context_record_digest(context)
        return freeze_dedun_analysis(
            request,
            memories,
            context_uid=context.uid,
            context_name=context.name,
            display_name=access.access_name,
            context_digest=digest,
            direct_memory_digest=direct_context_digest(context),
        )

    def _revalidated_access(self, plan: FrozenDedunPlan) -> ContextAccess:
        if not self.active_store.context_exists(plan.context_name):
            raise DedunConflictError(
                f"Dedun Context '{plan.context_name}' no longer exists."
            )
        return ContextAccess(
            store=self.active_store,
            context_name=plan.context_name,
            access_name=plan.display_name,
        )

    def apply(self, plan: FrozenDedunPlan, projection: DedunProjection) -> DedunReceipt:
        if not isinstance(plan, FrozenDedunPlan) or not isinstance(
            projection, DedunProjection
        ):
            raise TypeError("Dedun Apply requires a frozen plan and projection.")
        selections = projection.selections
        semantic_member_uids = {
            member.uid for component in plan.components for member in component.members
        }
        semantic_absorbed_uids = tuple(
            (uid for uid in projection.absorbed_uids if uid in semantic_member_uids)
        )
        survivor_uids = projection.survivor_uids
        absorbed_uids = projection.absorbed_uids
        access = self._revalidated_access(plan)
        current = access.store.load_for_update(access.context_name)
        if (
            current.uid != plan.context_uid
            or context_record_digest(current) != plan.context_digest
        ):
            raise DedunConflictError(
                "The Dedun Source changed before Apply; nothing was written."
            )
        for uid in semantic_absorbed_uids:
            if not isinstance(current.memories.get(uid), Memory):
                raise DedunConflictError(
                    f"Dedun Memory '{uid[:8]}' is no longer directly owned."
                )
        for uid in absorbed_uids:
            current.remove(uid)
        checkpoint = access.store.save(
            current,
            AutoCheckpointRequest(
                command="dedun",
                command_details={**dedun_projection_record(plan, projection)},
            ),
        )
        if checkpoint is None:
            raise DedunError(
                "Dedun Apply produced no checkpoint for a nonempty plan."
            )
        return DedunReceipt(
            context_uid=plan.context_uid,
            context_name=plan.display_name,
            revision=plan.revision,
            checkpoint_uid=checkpoint.uid,
            selections=selections,
            survivor_uids=survivor_uids,
            absorbed_uids=absorbed_uids,
        )


@dataclass(frozen=True)
class DedunScopeContextReceipt:
    """One direct Context effect inside an immediate recursive Dedun."""

    context_name: str
    context_uid: str
    group_count: int
    checkpoint_uid: str | None
    survivor_uids: tuple[str, ...]
    absorbed_uids: tuple[str, ...]


@dataclass(frozen=True)
class DedunScopeReceipt:
    """One atomic multi-Context Dedun command receipt."""

    root_name: str
    contexts: tuple[DedunScopeContextReceipt, ...]
    operation_uid: str | None
    include_descendants: bool = True

    @property
    def checkpoint_uids(self) -> tuple[str, ...]:
        return tuple(
            frame.checkpoint_uid
            for frame in self.contexts
            if frame.checkpoint_uid is not None
        )

    @property
    def absorbed_uids(self) -> tuple[str, ...]:
        return tuple(uid for frame in self.contexts for uid in frame.absorbed_uids)

    @property
    def survivor_uids(self) -> tuple[str, ...]:
        return tuple(uid for frame in self.contexts for uid in frame.survivor_uids)


__all__ = [
    "DedunScopeContextReceipt",
    "DedunScopeReceipt",
    "MemoryStoreDedunPort",
]
