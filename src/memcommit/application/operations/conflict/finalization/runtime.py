"""ProfileStore authority, freshness, and Apply boundary for Conflict."""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from memcommit.application.operations.audit.model import AuditTarget
from memcommit.application.context_access.access import (
    ContextAccess,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.operations.conflict.model import (
    CONFLICT_RESOLUTION_CONTRACT_VERSION,
    ConflictResolutionTarget,
    ConflictResolutionAnalysis,
    ConflictTargetChangedError,
    ConflictResolutionError,
    ConflictResolutionReceipt,
    ConflictResolutionRequest,
)
from memcommit.application.operations.conflict.review_round.finalize_review_decisions import (
    ConflictResolutionFinalizedInput,
)
from memcommit.application.operations.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdatePlan,
)
from memcommit.persistence.store import ProfileStore, context_record_digest

if TYPE_CHECKING:
    from memcommit.application.operations.audit.model import AuditCheckKind
    from memcommit.application.operations.audit.repository import AuditRecordRepository
    from ..application import ConflictResolutionProviderFactory, ConflictResolutionSemanticPort


def _revision(
    *,
    context_uid: str,
    context_name: str,
    display_name: str,
    context_digest: str,
    actionable_uids: tuple[str, ...],
) -> str:
    payload = {
        "contract": CONFLICT_RESOLUTION_CONTRACT_VERSION,
        "context": {
            "uid": context_uid,
            "name": context_name,
            "display_name": display_name,
            "digest": context_digest,
        },
        "actionable_uids": list(actionable_uids),
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


@dataclass
class ConflictResolutionStoreAdapter:
    """Adapt one Context scope to analysis and reviewed owner publication."""

    active_store: ProfileStore
    current_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.active_store, ProfileStore):
            raise TypeError("Conflict runtime requires a ProfileStore.")
        if self.current_name is None:
            self.current_name = self.active_store.current_context_name()
        if self.current_name is not None and (not isinstance(self.current_name, str)):
            raise TypeError("Conflict current Context snapshot must be text or None.")

    def _access(self, request: ConflictResolutionRequest) -> ContextAccess:
        if self.current_name is None:
            raise ConflictResolutionError(
                "No current Context. Run 'mem switch' or 'mem init' first."
            )
        if request.context_name not in (None, self.current_name):
            raise ConflictResolutionError(
                "Conflict can modify only the current Context; switch first."
            )
        return ContextAccess(
            store=self.active_store,
            context_name=self.current_name,
            access_name=self.current_name,
        )

    def load_conflict_resolution_target(self, request: ConflictResolutionRequest) -> ConflictResolutionTarget:
        if not isinstance(request, ConflictResolutionRequest):
            raise TypeError("Loading a Conflict target requires a typed request.")
        access = self._access(request)
        authority = access.store.load_direct(access.context_name)
        source = AuditTarget.from_context(authority)
        if len(source.items) < 2:
            raise ConflictResolutionError(
                "Conflict requires at least two Memories in the current Context."
            )
        actionable_uids = tuple(item.uid for item in source.items)
        return ConflictResolutionTarget(
            source=source,
            request=request,
            display_name=access.access_name,
            revision=_revision(
                context_uid=authority.uid,
                context_name=authority.name,
                display_name=access.access_name,
                context_digest=source.context_digest,
                actionable_uids=actionable_uids,
            ),
            actionable_uids=actionable_uids,
        )

    def _revalidated_access(self, frame: ConflictResolutionTarget) -> ContextAccess:
        if not self.active_store.context_exists(frame.source.context_name):
            raise ConflictTargetChangedError(
                f"Conflict Context '{frame.source.context_name}' no longer exists."
            )
        return ContextAccess(
            store=self.active_store,
            context_name=frame.source.context_name,
            access_name=frame.display_name,
        )

    @staticmethod
    def _require_current(frame: ConflictResolutionTarget, access: ContextAccess) -> Context:
        current = access.store.load_direct(access.context_name)
        if (
            current.uid != frame.source.context_uid
            or context_record_digest(current) != frame.source.context_digest
        ):
            raise ConflictTargetChangedError(
                "The Conflict Context changed during review. Reopen Conflict."
            )
        return current

    def revalidate(self, frame: ConflictResolutionTarget) -> None:
        if not isinstance(frame, ConflictResolutionTarget):
            raise TypeError("Conflict revalidation requires a reviewed frame.")
        access = self._revalidated_access(frame)
        self._require_current(frame, access)

    def apply_update_plan(
        self,
        frame: ConflictResolutionTarget,
        plan: UpdatePlan,
        *,
        unresolved_issue_uids: tuple[str, ...] = (),
        finalized_inputs: tuple[ConflictResolutionFinalizedInput, ...] = (),
    ) -> ConflictResolutionReceipt:
        """Publish one exact Update-generated plan through Conflict's lock."""
        if not isinstance(frame, ConflictResolutionTarget) or not isinstance(plan, UpdatePlan):
            raise TypeError("Conflict Apply requires a frozen frame and UpdatePlan.")
        if (
            plan.target_uid != frame.source.context_uid
            or plan.target_name != frame.source.context_name
        ):
            raise ConflictTargetChangedError(
                "Conflict UpdatePlan does not name its frozen target Context."
            )
        if (
            not isinstance(unresolved_issue_uids, tuple)
            or len(set(unresolved_issue_uids)) != len(unresolved_issue_uids)
            or any(
                (not isinstance(uid, str) or not uid for uid in unresolved_issue_uids)
            )
        ):
            raise ConflictResolutionError("Conflict unresolved Issue identities are invalid.")
        if not isinstance(finalized_inputs, tuple) or any(
            (not isinstance(value, ConflictResolutionFinalizedInput) for value in finalized_inputs)
        ):
            raise TypeError("Conflict finalized inputs must use the typed contract.")
        effect_by_type = {
            AddOperation: "CREATE",
            EditOperation: "UPDATE",
            RemoveOperation: "DELETE",
        }
        effect_labels = tuple(
            (effect_by_type.get(type(operation)) for operation in plan.operations)
        )
        if any((label is None for label in effect_labels)):
            raise ConflictResolutionError("Conflict UpdatePlan contains an unsupported operation.")
        if any(
            (
                operation.owner_context_uid != frame.source.context_uid
                or operation.owner_context_name != frame.source.context_name
                for operation in plan.operations
            )
        ):
            raise ConflictTargetChangedError(
                "Conflict UpdatePlan names an owner outside its frozen Context."
            )
        access = self._revalidated_access(frame)
        # Revalidate the frozen frame before publishing its effects.
        current = access.store.load_for_update(access.context_name)
        if (
            current.uid != frame.source.context_uid
            or context_record_digest(current) != frame.source.context_digest
        ):
            raise ConflictTargetChangedError(
                "The Conflict Context changed before Apply; nothing was written."
            )
        for operation in plan.operations:
            current_item = current.memories.get(operation.memory_uid)
            if isinstance(operation, AddOperation):
                if current_item is not None:
                    raise ConflictTargetChangedError(
                        "Conflict addition uid already exists in the target."
                    )
                current.add(Memory(operation.memory_uid, operation.new_content))
            elif isinstance(operation, EditOperation):
                if (
                    not isinstance(current_item, Memory)
                    or current_item.content != operation.old_content
                ):
                    raise ConflictTargetChangedError(
                        "Conflict edit target no longer matches its pre-image."
                    )
                current.replace_memory(
                    Memory(operation.memory_uid, operation.new_content)
                )
            else:
                assert isinstance(operation, RemoveOperation)
                if (
                    not isinstance(current_item, Memory)
                    or current_item.content != operation.old_content
                ):
                    raise ConflictTargetChangedError(
                        "Conflict removal target no longer matches its pre-image."
                    )
                current.remove(operation.memory_uid)
        checkpoint = access.store.save(
            current,
            AutoCheckpointRequest(
                command="conflict",
                command_details={
                    "contract": CONFLICT_RESOLUTION_CONTRACT_VERSION,
                    "revision": frame.revision,
                    "update_plan_uid": plan.uid,
                    "update_plan_digest": plan.digest,
                    "effects": [
                        operation.to_dict() for operation in plan.operations
                    ],
                    "finalized_inputs": [
                        value.to_dict() for value in finalized_inputs
                    ],
                    "unresolved_issue_uids": list(unresolved_issue_uids),
                },
            ),
        )
        if checkpoint is None:
            raise ConflictResolutionError(
                "Conflict Apply produced no checkpoint for its UpdatePlan."
            )
        return ConflictResolutionReceipt(
            context_uid=frame.source.context_uid,
            context_name=frame.display_name,
            revision=frame.revision,
            plan_uid=plan.uid,
            checkpoint_uid=checkpoint.uid,
            created_uids=tuple(
                (
                    operation.memory_uid
                    for operation in plan.operations
                    if isinstance(operation, AddOperation)
                )
            ),
            updated_uids=tuple(
                (
                    operation.memory_uid
                    for operation in plan.operations
                    if isinstance(operation, EditOperation)
                )
            ),
            deleted_uids=tuple(
                (
                    operation.memory_uid
                    for operation in plan.operations
                    if isinstance(operation, RemoveOperation)
                )
            ),
            unresolved_issue_uids=unresolved_issue_uids,
        )


def analyze_context_conflicts_from_store(
    request: ConflictResolutionRequest,
    *,
    store_port: ConflictResolutionStoreAdapter,
    checks: frozenset[AuditCheckKind],
    semantic_port: ConflictResolutionSemanticPort,
    audit_repository: AuditRecordRepository,
    audit_provider_factory: ConflictResolutionProviderFactory,
    direction_provider_factory: ConflictResolutionProviderFactory,
    expected_revision: str | None = None,
) -> ConflictResolutionAnalysis:
    """Acquire a Store input and recheck it before publishing its analysis."""
    from ..application import analyze_conflicts_for_resolution

    frame = store_port.load_conflict_resolution_target(request)
    store_port.revalidate(frame)
    analysis = analyze_conflicts_for_resolution(
        frame,
        checks=checks,
        semantic_port=semantic_port,
        audit_repository=audit_repository,
        audit_provider_factory=audit_provider_factory,
        direction_provider_factory=direction_provider_factory,
        expected_revision=expected_revision,
    )
    store_port.revalidate(frame)
    return analysis


__all__ = ["ConflictResolutionStoreAdapter", "analyze_context_conflicts_from_store"]
