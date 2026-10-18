"""MemoryStore authority, freshness, and Apply boundary for Resolve."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from memcommit.application.operations.audit.model import (
    QualityAuditMemory,
    AuditTarget,
)
from memcommit.application.authorization.context_operation import (
    authorized_context_mutation,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    grant_checkpoint_args,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.capabilities.context_scope_loading import (
    load_mutable_context_scope,
    walk_context_owners,
)
from memcommit.application.capabilities.context_memory_target import ContextMemoryTarget
from memcommit.application.capabilities.semantic.changes import (
    get_required_permission_for_effect,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.application.operations.resolve.model import (
    RESOLVE_CONTRACT_VERSION,
    ResolveTarget,
    ResolveAuthorityError,
    ResolveAnalysis,
    ResolveConflictError,
    ResolveEffectKind,
    ResolveError,
    ResolveReceipt,
    ResolveRequest,
)
from memcommit.application.operations.resolve.review_round.finalize_review_decisions import (
    ResolveFinalizedInput,
)
from memcommit.application.operations.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdatePlan,
)
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    find_exact_duplicate_groups,
)

if TYPE_CHECKING:
    from memcommit.application.capabilities.context_memory_target import (
        ContextMemoryOrigin,
    )
    from memcommit.application.operations.audit.model import AuditCheckKind
    from memcommit.application.operations.audit.repository import AuditRecordRepository
    from ..application import ResolveProviderFactory, ResolveSemanticPort


_EFFECT_PERMISSION_ORDER: tuple[ResolveEffectKind, ...] = (
    "CREATE",
    "UPDATE",
    "DELETE",
)


def _revision(
    request: ResolveRequest,
    *,
    context_uid: str,
    context_name: str,
    display_name: str,
    context_digest: str,
    actionable_uids: tuple[str, ...],
    owner_records: tuple[tuple[str, str, str], ...] = (),
) -> str:
    payload = {
        "contract": RESOLVE_CONTRACT_VERSION,
        "context": {
            "uid": context_uid,
            "name": context_name,
            "display_name": display_name,
            "digest": context_digest,
        },
        "actionable_uids": list(actionable_uids),
        "requested_effects": list(request.requested_effects),
        "guidance": request.guidance,
        "recursive": request.recursive,
        **({"owners": owner_records} if owner_records else {}),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _select_actionable(
    memories: tuple[QualityAuditMemory, ...],
    selectors: tuple[str, ...],
) -> tuple[str, ...]:
    if not selectors:
        return tuple(memory.uid for memory in memories)
    selected: list[str] = []
    for selector in selectors:
        matches = tuple(
            memory for memory in memories if memory.uid.startswith(selector)
        )
        if not matches:
            raise ResolveError(
                f"No direct Memory has a uid starting with '{selector}'."
            )
        if len(matches) > 1:
            raise ResolveError(
                f"Ambiguous prefix '{selector}' matches {len(matches)} Memories: "
                + ", ".join(memory.uid[:8] for memory in matches)
            )
        if matches[0].uid in selected:
            raise ResolveError(
                f"Resolve selectors repeat Memory '{matches[0].uid[:8]}'."
            )
        selected.append(matches[0].uid)
    return tuple(selected)


@dataclass
class ResolveStoreAdapter:
    """Adapt one Context scope to analysis and reviewed owner publication."""

    active_store: MemoryStore
    current_name: str | None = None
    registry: ProfileRegistry | None = None
    allow_grants: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.active_store, MemoryStore):
            raise TypeError("Resolve runtime requires a MemoryStore.")
        if self.current_name is not None and not isinstance(self.current_name, str):
            raise TypeError("Resolve current Context snapshot must be text or None.")
        if not isinstance(self.allow_grants, bool):
            raise TypeError("Resolve grant availability must be boolean.")

    def _access(self, request: ResolveRequest) -> ContextAccess:
        operand = request.context_name or self.current_name
        if operand is None:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        canonical = resolve_context_locator(operand, current=self.current_name)
        if not self.allow_grants and not self.active_store.context_exists(canonical):
            raise FileNotFoundError(f"Context '{canonical}' not found.")
        return resolve_context_access(
            self.active_store,
            request.context_name,
            current_name=self.current_name,
            required_permission="READ",
            registry=self.registry,
        )

    def _records(self, access: ContextAccess) -> tuple[Context, Context]:
        authority = access.store.load_direct(access.context_name)
        if access.is_granted:
            projected = GrantedReadStore(
                access,
                registry=self.registry,
            ).load_direct(access.access_name)
            if projected.uid != authority.uid:
                raise ResolveConflictError(
                    "Granted Resolve Context identity changed during projection."
                )
            return authority, projected
        return authority, authority

    def load_resolve_target(self, request: ResolveRequest) -> ResolveTarget:
        if not isinstance(request, ResolveRequest):
            raise TypeError("Loading a Resolve target requires a typed request.")
        access = self._access(request)
        authority, projected = self._records(access)
        memory_target = None
        if request.recursive:
            memory_target = ContextMemoryTarget.from_context(
                load_mutable_context_scope(
                    self.active_store, access, registry=self.registry
                )
            )
            source = AuditTarget.from_context(memory_target.analysis_context())
        else:
            source = AuditTarget.from_context(authority)
        # A Grant projection may rename the Context, but cannot change its Memories.
        if (
            not request.recursive
            and access.is_granted
            and tuple(
                (item.uid, item.content)
                for item in projected.iter_items()
                if isinstance(item, Memory)
            )
            != tuple((item.uid, item.content) for item in source.memories)
        ):
            raise ResolveError("Resolve Source and Memory projection disagree.")
        if len(source.items) < 2:
            raise ResolveError(
                "Resolve requires at least two items in the selected Context scope."
            )
        if memory_target is not None and request.memory_selectors:
            from memcommit.core.context_targeting.resolution import (
                parse_direct_memory_locator,
            )

            selected = []
            for selector in request.memory_selectors:
                locator = parse_direct_memory_locator(selector)
                matches = tuple(
                    origin
                    for origin in memory_target.origins
                    if origin.memory_uid.startswith(locator.memory_selector)
                    and (
                        locator.context_locator is None
                        or origin.context_name == locator.context_locator
                    )
                )
                if len(matches) != 1:
                    raise ResolveError(
                        f"Recursive Memory selector '{selector}' matches {len(matches)} Memories in the target; qualify it with CONTEXT:UID."
                    )
                if matches[0].analysis_uid in selected:
                    raise ResolveError("Resolve selectors repeat a Memory.")
                selected.append(matches[0].analysis_uid)
            actionable_uids = tuple(selected)
        else:
            actionable_uids = (
                _select_actionable(source.memories, request.memory_selectors)
                if request.memory_selectors
                else tuple(item.uid for item in source.items)
            )
        requested = request.requested_effects
        grant_permissions = (
            set(access.view.grant.permissions) if access.view is not None else None
        )
        if grant_permissions is None:
            allowed = requested
            denied: tuple[ResolveEffectKind, ...] = ()
            missing_authority: tuple[str, ...] = ()
            binding = None
        else:
            allowed = tuple(
                effect
                for effect in requested
                if get_required_permission_for_effect(effect) in grant_permissions
            )
            denied = tuple(
                effect
                for effect in requested
                if get_required_permission_for_effect(effect) not in grant_permissions
            )
            missing_authority = ()
            binding = freeze_granted_context_binding(access)
        return ResolveTarget(
            source=source,
            request=request,
            display_name=access.access_name,
            revision=_revision(
                request,
                context_uid=authority.uid,
                context_name=authority.name,
                display_name=access.access_name,
                context_digest=source.context_digest,
                actionable_uids=actionable_uids,
                owner_records=tuple(
                    (
                        owner.uid,
                        owner.name,
                        owner._store_digest or context_record_digest(owner),
                    )
                    for owner in walk_context_owners(memory_target.graph)
                )
                if memory_target
                else (),
            ),
            actionable_uids=actionable_uids,
            allowed_effects=allowed,
            denied_effects=denied,
            missing_authority=missing_authority,
            granted_binding=binding,
            memory_target=memory_target,
        )

    def _revalidated_access(self, frame: ResolveTarget) -> ContextAccess:
        if frame.granted_binding is not None:
            try:
                return revalidate_granted_context_binding(
                    frame.granted_binding,
                    required_permission="READ",
                    active_store=self.active_store,
                )
            except Exception as error:
                raise ResolveAuthorityError(str(error)) from error
        if not self.active_store.context_exists(frame.source.context_name):
            raise ResolveConflictError(
                f"Resolve Context '{frame.source.context_name}' no longer exists."
            )
        return ContextAccess(
            store=self.active_store,
            context_name=frame.source.context_name,
            access_name=frame.display_name,
            permission="READ",
        )

    @staticmethod
    def _require_current(frame: ResolveTarget, access: ContextAccess) -> Context:
        current = access.store.load_direct(access.context_name)
        if (
            current.uid != frame.source.context_uid
            or context_record_digest(current) != frame.source.context_digest
        ):
            raise ResolveConflictError(
                "The Resolve Context changed during review. Reopen Resolve."
            )
        return current

    def revalidate(self, frame: ResolveTarget) -> None:
        if frame.memory_target is not None:
            from .publish_recursive_resolve import revalidate_recursive_target

            revalidate_recursive_target(self, frame)
            return
        if not isinstance(frame, ResolveTarget):
            raise TypeError("Resolve revalidation requires a reviewed frame.")
        access = self._revalidated_access(frame)
        if access.view is not None:
            permissions = set(access.view.grant.permissions)
            required = {
                "READ",
                *(get_required_permission_for_effect(effect) for effect in frame.allowed_effects),
            }
            missing = tuple(sorted(required - permissions))
            if missing:
                raise ResolveAuthorityError(
                    "Resolve Grant lost required authority: " + ", ".join(missing)
                )
        self._require_current(frame, access)

    @staticmethod
    def _inbound_references(
        store: MemoryStore,
        *,
        context_uid: str,
        deleted_uids: set[str],
    ) -> tuple[tuple[str, str], ...]:
        if not deleted_uids:
            return ()
        inbound: list[tuple[str, str]] = []
        for context in store.load_direct_context_graph_strict():
            for item in context.iter_items():
                if (
                    isinstance(item, MemoryRef)
                    and item.target_context_uid == context_uid
                    and item.target_memory_uid in deleted_uids
                ):
                    inbound.append((context.name, item.uid))
        return tuple(inbound)

    def apply_update_plan(
        self,
        frame: ResolveTarget,
        plan: UpdatePlan,
        *,
        unresolved_issue_uids: tuple[str, ...] = (),
        finalized_inputs: tuple[ResolveFinalizedInput, ...] = (),
        removed_item_uids: tuple[str, ...] = (),
        memory_origins: tuple[ContextMemoryOrigin, ...] = (),
    ) -> ResolveReceipt:
        """Publish one exact Update-generated plan through Resolve's lock."""

        if not isinstance(frame, ResolveTarget) or not isinstance(plan, UpdatePlan):
            raise TypeError("Resolve Apply requires a frozen frame and UpdatePlan.")
        if (
            plan.target_uid != frame.source.context_uid
            or plan.target_name != frame.source.context_name
        ):
            raise ResolveConflictError(
                "Resolve UpdatePlan does not name its frozen target Context."
            )
        if (
            not isinstance(unresolved_issue_uids, tuple)
            or len(set(unresolved_issue_uids)) != len(unresolved_issue_uids)
            or any(not isinstance(uid, str) or not uid for uid in unresolved_issue_uids)
        ):
            raise ResolveError("Resolve unresolved Issue identities are invalid.")
        if not isinstance(finalized_inputs, tuple) or any(
            not isinstance(value, ResolveFinalizedInput) for value in finalized_inputs
        ):
            raise TypeError("Resolve finalized inputs must use the typed contract.")

        if frame.memory_target is not None:
            from .publish_recursive_resolve import publish_recursive_resolve

            return publish_recursive_resolve(
                self,
                frame,
                plan,
                unresolved_issue_uids=unresolved_issue_uids,
                finalized_inputs=finalized_inputs,
                removed_item_uids=removed_item_uids,
                memory_origins=memory_origins,
            )

        eligible = {
            uid
            for group in find_exact_duplicate_groups(frame.source.context())
            if group.item_kind != "MEMORY"
            for uid in group.absorbed_uids
        }
        if (
            not isinstance(removed_item_uids, tuple)
            or any(not isinstance(uid, str) for uid in removed_item_uids)
            or len(set(removed_item_uids)) != len(removed_item_uids)
            or not set(removed_item_uids) <= eligible
        ):
            raise ResolveError(
                "Resolve structural removals must name frozen exact duplicate placements."
            )
        effect_by_type = {
            AddOperation: "CREATE",
            EditOperation: "UPDATE",
            RemoveOperation: "DELETE",
        }
        effect_labels = tuple(
            effect_by_type.get(type(operation)) for operation in plan.operations
        ) + (("DELETE",) if removed_item_uids else ())
        if any(label is None for label in effect_labels):
            raise ResolveError("Resolve UpdatePlan contains an unsupported operation.")
        if any(label not in frame.allowed_effects for label in effect_labels):
            raise ResolveAuthorityError(
                "Resolve UpdatePlan exceeds the finalized effect capabilities."
            )
        if any(
            operation.owner_context_uid != frame.source.context_uid
            or operation.owner_context_name != frame.source.context_name
            for operation in plan.operations
        ):
            raise ResolveConflictError(
                "Resolve UpdatePlan names an owner outside its frozen Context."
            )

        required_permissions = (
            "READ",
            *(
                get_required_permission_for_effect(effect)
                for effect in _EFFECT_PERMISSION_ORDER
                if effect in effect_labels
            ),
        )
        if not plan.operations and not removed_item_uids:
            # A force-only Resolve still writes its audit checkpoint. Require
            # one reviewed mutation capability instead of treating that write
            # as though READ authority alone permitted it.
            required_permissions = (
                "READ",
                get_required_permission_for_effect(frame.allowed_effects[0]),
            )
        deleted_uids = {
            operation.memory_uid
            for operation in plan.operations
            if isinstance(operation, RemoveOperation)
        }
        access = self._revalidated_access(frame)
        with authorized_context_mutation(
            access,
            required_permissions=required_permissions,
        ):
            # Resolve owns publication and audit, while Update owns the exact
            # plan. Keep the source scan, CAS, and checkpoint in one lock.
            with access.store._command_write_lock():  # noqa: SLF001
                current = access.store.load_for_update(access.context_name)
                if (
                    current.uid != frame.source.context_uid
                    or context_record_digest(current) != frame.source.context_digest
                ):
                    raise ResolveConflictError(
                        "The Resolve Context changed before Apply; nothing was written."
                    )
                inbound = self._inbound_references(
                    access.store,
                    context_uid=frame.source.context_uid,
                    deleted_uids=deleted_uids,
                )
                if inbound:
                    locations = ", ".join(
                        f"{owner}#{reference_uid[:8]}"
                        for owner, reference_uid in inbound
                    )
                    raise ResolveConflictError(
                        "Resolve cannot delete Memories with inbound references: "
                        + locations
                    )
                for operation in plan.operations:
                    current_item = current.memories.get(operation.memory_uid)
                    if isinstance(operation, AddOperation):
                        if current_item is not None:
                            raise ResolveConflictError(
                                "Resolve addition uid already exists in the target."
                            )
                        current.add(Memory(operation.memory_uid, operation.new_content))
                    elif isinstance(operation, EditOperation):
                        if (
                            not isinstance(current_item, Memory)
                            or current_item.content != operation.old_content
                        ):
                            raise ResolveConflictError(
                                "Resolve edit target no longer matches its pre-image."
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
                            raise ResolveConflictError(
                                "Resolve removal target no longer matches its pre-image."
                            )
                        current.remove(operation.memory_uid)

                # Remove only the local redundant placements. Never mutate
                # their referenced Context or Memory, even for live embeds.
                for uid in removed_item_uids:
                    current.remove(uid)

                checkpoint = access.store._save_command_locked(  # noqa: SLF001
                    current,
                    AutoCheckpoint(
                        command="resolve",
                        args={
                            "contract": RESOLVE_CONTRACT_VERSION,
                            "revision": frame.revision,
                            "update_plan_uid": plan.uid,
                            "update_plan_digest": plan.digest,
                            "removed_item_uids": list(removed_item_uids),
                            "effects": [
                                operation.to_dict() for operation in plan.operations
                            ],
                            "finalized_inputs": [
                                value.to_dict() for value in finalized_inputs
                            ],
                            "unresolved_issue_uids": list(unresolved_issue_uids),
                            "guidance": frame.request.guidance,
                            **grant_checkpoint_args(access),
                        },
                        description=(
                            f"Resolved {len(plan.operations)} Memory effect(s) and {len(removed_item_uids)} duplicate placement(s) "
                            "from finalized decisions"
                        ),
                    ),
                    expected_context_digest=frame.source.context_digest,
                )
                if checkpoint is None:
                    raise ResolveError(
                        "Resolve Apply produced no checkpoint for its UpdatePlan."
                    )

        return ResolveReceipt(
            context_uid=frame.source.context_uid,
            context_name=frame.display_name,
            revision=frame.revision,
            plan_uid=plan.uid,
            checkpoint_uid=checkpoint.uid,
            created_uids=tuple(
                operation.memory_uid
                for operation in plan.operations
                if isinstance(operation, AddOperation)
            ),
            updated_uids=tuple(
                operation.memory_uid
                for operation in plan.operations
                if isinstance(operation, EditOperation)
            ),
            deleted_uids=tuple(
                operation.memory_uid
                for operation in plan.operations
                if isinstance(operation, RemoveOperation)
            )
            + removed_item_uids,
            unresolved_issue_uids=unresolved_issue_uids,
        )


def run_resolve_from_store(
    request: ResolveRequest,
    *,
    store_port: ResolveStoreAdapter,
    checks: frozenset[AuditCheckKind],
    semantic_port: ResolveSemanticPort,
    audit_repository: AuditRecordRepository,
    audit_provider_factory: ResolveProviderFactory,
    direction_provider_factory: ResolveProviderFactory,
    expected_revision: str | None = None,
) -> ResolveAnalysis:
    """Acquire a Store input and recheck it before publishing its analysis."""
    from ..application import run_resolve

    frame = store_port.load_resolve_target(request)
    store_port.revalidate(frame)
    analysis = run_resolve(
        frame,
        checks=checks,
        semantic_port=semantic_port,
        audit_repository=audit_repository,
        audit_provider_factory=audit_provider_factory,
        direction_provider_factory=direction_provider_factory,
        expected_revision=expected_revision,
    )
    # Provider work uses snapshot copies; only this Store boundary checks live state.
    store_port.revalidate(frame)
    return analysis


__all__ = ["ResolveStoreAdapter", "run_resolve_from_store"]
