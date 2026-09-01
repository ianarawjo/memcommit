"""MemoryStore authority, freshness, and Apply boundary for Resolve."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

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
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.application.operations.resolve.application import (
    RESOLVE_CONTRACT_VERSION,
    FrozenResolveFrame,
    ResolveAuthorityError,
    ResolveConflictError,
    ResolveEffectKind,
    ResolveError,
    ResolveFrameMemory,
    ResolveReceipt,
    ResolveRequest,
)
from memcommit.application.operations.resolve.decisions import (
    ResolveFinalizedInput,
)
from memcommit.application.operations.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdatePlan,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


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
    memories: tuple[ResolveFrameMemory, ...],
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
class MemoryStoreResolvePort:
    """Resolve one exact Context through a fixed active Store boundary."""

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

    def freeze(self, request: ResolveRequest) -> FrozenResolveFrame:
        if not isinstance(request, ResolveRequest):
            raise TypeError("Resolve freeze requires a typed request.")
        access = self._access(request)
        authority, projected = self._records(access)
        memories = tuple(
            ResolveFrameMemory(
                alias=f"m{index}",
                uid=item.uid,
                content=item.content,
            )
            for index, item in enumerate(
                (
                    value
                    for value in projected.iter_items()
                    if isinstance(value, Memory)
                ),
                1,
            )
        )
        if len(memories) < 2:
            raise ResolveError(
                "Resolve requires at least two directly owned Memories in the "
                "selected Context."
            )
        actionable_uids = _select_actionable(memories, request.memory_selectors)
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
                effect for effect in requested if effect in grant_permissions
            )
            denied = tuple(
                effect for effect in requested if effect not in grant_permissions
            )
            missing_authority = ()
            binding = freeze_granted_context_binding(access)
        digest = context_record_digest(authority)
        return FrozenResolveFrame(
            request=request,
            context_uid=authority.uid,
            context_name=authority.name,
            display_name=access.access_name,
            context_digest=digest,
            revision=_revision(
                request,
                context_uid=authority.uid,
                context_name=authority.name,
                display_name=access.access_name,
                context_digest=digest,
                actionable_uids=actionable_uids,
            ),
            memories=memories,
            actionable_uids=actionable_uids,
            allowed_effects=allowed,
            denied_effects=denied,
            missing_authority=missing_authority,
            granted_binding=binding,
        )

    def _revalidated_access(self, frame: FrozenResolveFrame) -> ContextAccess:
        if frame.granted_binding is not None:
            try:
                return revalidate_granted_context_binding(
                    frame.granted_binding,
                    required_permission="READ",
                    active_store=self.active_store,
                )
            except Exception as error:
                raise ResolveAuthorityError(str(error)) from error
        if not self.active_store.context_exists(frame.context_name):
            raise ResolveConflictError(
                f"Resolve Context '{frame.context_name}' no longer exists."
            )
        return ContextAccess(
            store=self.active_store,
            context_name=frame.context_name,
            access_name=frame.display_name,
            permission="READ",
        )

    @staticmethod
    def _require_current(frame: FrozenResolveFrame, access: ContextAccess) -> Context:
        current = access.store.load_direct(access.context_name)
        if (
            current.uid != frame.context_uid
            or context_record_digest(current) != frame.context_digest
        ):
            raise ResolveConflictError(
                "The Resolve Context changed during review. Reopen Resolve."
            )
        return current

    def revalidate(self, frame: FrozenResolveFrame) -> None:
        if not isinstance(frame, FrozenResolveFrame):
            raise TypeError("Resolve revalidation requires a reviewed frame.")
        access = self._revalidated_access(frame)
        if access.view is not None:
            permissions = set(access.view.grant.permissions)
            required = {"READ", *frame.allowed_effects}
            missing = tuple(sorted(required - permissions))
            if missing:
                raise ResolveAuthorityError(
                    "Resolve Grant lost required authority: " + ", ".join(missing)
                )
        self._require_current(frame, access)

    def load_target(self, frame: FrozenResolveFrame) -> Context:
        """Return the exact detached authority Context bound by ``frame``."""

        if not isinstance(frame, FrozenResolveFrame):
            raise TypeError("Resolve Target loading requires a frozen frame.")
        access = self._revalidated_access(frame)
        current = self._require_current(frame, access)
        target = Context.from_dict(current.to_dict())
        target._store_digest = current._store_digest
        return target

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
        frame: FrozenResolveFrame,
        plan: UpdatePlan,
        *,
        unresolved_issue_uids: tuple[str, ...] = (),
        finalized_inputs: tuple[ResolveFinalizedInput, ...] = (),
    ) -> ResolveReceipt:
        """Publish one exact Update-generated plan through Resolve's lock."""

        if not isinstance(frame, FrozenResolveFrame) or not isinstance(
            plan, UpdatePlan
        ):
            raise TypeError("Resolve Apply requires a frozen frame and UpdatePlan.")
        if plan.target_uid != frame.context_uid or plan.target_name != frame.context_name:
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
            not isinstance(value, ResolveFinalizedInput)
            for value in finalized_inputs
        ):
            raise TypeError("Resolve finalized inputs must use the typed contract.")

        effect_by_type = {
            AddOperation: "CREATE",
            EditOperation: "UPDATE",
            RemoveOperation: "DELETE",
        }
        effect_labels = tuple(
            effect_by_type.get(type(operation)) for operation in plan.operations
        )
        if any(label is None for label in effect_labels):
            raise ResolveError("Resolve UpdatePlan contains an unsupported operation.")
        if any(label not in frame.allowed_effects for label in effect_labels):
            raise ResolveAuthorityError(
                "Resolve UpdatePlan exceeds the finalized effect capabilities."
            )
        if any(
            operation.owner_context_uid != frame.context_uid
            or operation.owner_context_name != frame.context_name
            for operation in plan.operations
        ):
            raise ResolveConflictError(
                "Resolve UpdatePlan names an owner outside its frozen Context."
            )

        required_permissions = (
            "READ",
            *(
                effect
                for effect in _EFFECT_PERMISSION_ORDER
                if effect in effect_labels
            ),
        )
        if not plan.operations:
            # A force-only Resolve still writes its audit checkpoint. Require
            # one reviewed mutation capability instead of treating that write
            # as though READ authority alone permitted it.
            required_permissions = ("READ", frame.allowed_effects[0])
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
                    current.uid != frame.context_uid
                    or context_record_digest(current) != frame.context_digest
                ):
                    raise ResolveConflictError(
                        "The Resolve Context changed before Apply; nothing was written."
                    )
                inbound = self._inbound_references(
                    access.store,
                    context_uid=frame.context_uid,
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
                        current.replace(
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

                checkpoint = access.store._save_command_locked(  # noqa: SLF001
                    current,
                    AutoCheckpoint(
                        command="resolve",
                        args={
                            "contract": RESOLVE_CONTRACT_VERSION,
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
                            "guidance": frame.request.guidance,
                            **grant_checkpoint_args(access),
                        },
                        description=(
                            f"Resolved {len(plan.operations)} Memory effect(s) "
                            "from finalized decisions"
                        ),
                    ),
                    expected_context_digest=frame.context_digest,
                )
                if checkpoint is None:
                    raise ResolveError(
                        "Resolve Apply produced no checkpoint for its UpdatePlan."
                    )

        return ResolveReceipt(
            context_uid=frame.context_uid,
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
            ),
            unresolved_issue_uids=unresolved_issue_uids,
        )


__all__ = ["MemoryStoreResolvePort"]
