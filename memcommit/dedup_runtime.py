"""MemoryStore authority, freshness, and atomic Apply boundary for Dedup."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from memcommit.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    freeze_granted_context_binding,
    grant_checkpoint_args,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint, Memory, MemoryRef
from memcommit.dedup_application import (
    DEDUP_CONTRACT_VERSION,
    DedupAuthorityError,
    DedupConflictError,
    DedupError,
    DedupReceipt,
    DedupRequest,
    DedupSelection,
    FrozenDedupPlan,
    validate_dedup_selections,
)
from memcommit.dedup_planning import build_dedup_components
from memcommit.profile_config import ProfileRegistry
from memcommit.review import direct_context_digest
from memcommit.store import MemoryStore, context_record_digest


def _revision(
    request: DedupRequest,
    *,
    context_uid: str,
    context_name: str,
    display_name: str,
    context_digest: str,
    component_uids: tuple[str, ...],
) -> str:
    payload = {
        "contract": DEDUP_CONTRACT_VERSION,
        "context": {
            "uid": context_uid,
            "name": context_name,
            "display_name": display_name,
            "digest": context_digest,
        },
        "components": list(component_uids),
        "handoffs": [handoff.uid for handoff in request.handoffs],
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


@dataclass
class MemoryStoreDedupPort:
    """Apply confirmed duplicate components in one exact Context."""

    active_store: MemoryStore
    current_name: str | None = None
    registry: ProfileRegistry | None = None
    allow_grants: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.active_store, MemoryStore):
            raise TypeError("Dedun runtime requires a MemoryStore.")
        if not isinstance(self.allow_grants, bool):
            raise TypeError("Dedun grant availability must be boolean.")

    def _access(self, request: DedupRequest) -> ContextAccess:
        source = request.source
        if (
            not self.allow_grants
            and not self.active_store.context_exists(source.display_name)
        ):
            raise FileNotFoundError(f"Context '{source.display_name}' not found.")
        return resolve_context_access(
            self.active_store,
            source.display_name,
            current_name=self.current_name,
            required_permission="READ",
            registry=self.registry,
        )

    @staticmethod
    def _require_grant_permissions(access: ContextAccess) -> None:
        if access.view is None:
            return
        missing = sorted(
            {"READ", "DERIVE", "DELETE"} - set(access.view.grant.permissions)
        )
        if missing:
            raise DedupAuthorityError(
                "Dedun Grant lacks required authority: " + ", ".join(missing)
            )

    def freeze(self, request: DedupRequest) -> FrozenDedupPlan:
        if not isinstance(request, DedupRequest):
            raise TypeError("Dedun freeze requires a typed request.")
        access = self._access(request)
        self._require_grant_permissions(access)
        source = request.source
        context = access.store.load_direct(access.context_name)
        if context.uid != source.context_uid or access.display_name != source.display_name:
            raise DedupConflictError(
                "The confirmed duplicate Source identity changed. Run the finder again."
            )
        if direct_context_digest(context) != source.direct_memory_digest:
            raise DedupConflictError(
                "The confirmed duplicate Source changed. Run the finder again."
            )
        memories = tuple(
            item for item in context.iter_items() if isinstance(item, Memory)
        )
        components = build_dedup_components(request, memories)
        digest = context_record_digest(context)
        return FrozenDedupPlan(
            request=request,
            context_uid=context.uid,
            context_name=context.name,
            display_name=access.display_name,
            context_digest=digest,
            revision=_revision(
                request,
                context_uid=context.uid,
                context_name=context.name,
                display_name=access.display_name,
                context_digest=digest,
                component_uids=tuple(component.uid for component in components),
            ),
            components=components,
            granted_binding=(
                freeze_granted_context_binding(access)
                if access.view is not None
                else None
            ),
        )

    def _revalidated_access(self, plan: FrozenDedupPlan) -> ContextAccess:
        if plan.granted_binding is not None:
            try:
                access = revalidate_granted_context_binding(
                    plan.granted_binding,
                    required_permission="READ",
                    active_store=self.active_store,
                    registry=self.registry,
                )
            except Exception as error:
                raise DedupAuthorityError(str(error)) from error
            self._require_grant_permissions(access)
            return access
        if not self.active_store.context_exists(plan.context_name):
            raise DedupConflictError(
                f"Dedun Context '{plan.context_name}' no longer exists."
            )
        return ContextAccess(
            store=self.active_store,
            context_name=plan.context_name,
            display_name=plan.display_name,
            attachment_name=None,
            permission="READ",
        )

    @staticmethod
    def _inbound_references(
        store: MemoryStore,
        *,
        context_uid: str,
        absorbed_uids: set[str],
    ) -> tuple[tuple[str, str], ...]:
        inbound: list[tuple[str, str]] = []
        for context in store.load_direct_context_graph_strict():
            for item in context.iter_items():
                if (
                    isinstance(item, MemoryRef)
                    and item.target_context_uid == context_uid
                    and item.target_memory_uid in absorbed_uids
                ):
                    inbound.append((context.name, item.uid))
        return tuple(inbound)

    def apply(
        self,
        plan: FrozenDedupPlan,
        selections: tuple[DedupSelection, ...],
    ) -> DedupReceipt:
        if not isinstance(plan, FrozenDedupPlan) or any(
            not isinstance(selection, DedupSelection) for selection in selections
        ):
            raise TypeError("Dedun Apply requires a frozen plan and selections.")
        selections = validate_dedup_selections(plan, selections)
        survivor_uids = tuple(selection.survivor_uid for selection in selections)
        absorbed_uids = tuple(
            member.uid
            for component, selection in zip(plan.components, selections)
            for member in component.members
            if member.uid != selection.survivor_uid
        )
        if not absorbed_uids:
            raise DedupError("Dedun Apply requires at least one absorbed Memory.")
        access = self._revalidated_access(plan)
        with authorized_context_mutation(
            access,
            required_permissions=("READ", "DERIVE", "DELETE"),
        ):
            # Scan and mutation share the command lock so a new inbound pointer
            # cannot appear between reference validation and deletion.
            with access.store._command_write_lock():  # noqa: SLF001
                current = access.store.load_for_update(access.context_name)
                if (
                    current.uid != plan.context_uid
                    or context_record_digest(current) != plan.context_digest
                ):
                    raise DedupConflictError(
                        "The Dedun Source changed before Apply; nothing was written."
                    )
                inbound = self._inbound_references(
                    access.store,
                    context_uid=plan.context_uid,
                    absorbed_uids=set(absorbed_uids),
                )
                if inbound:
                    locations = ", ".join(
                        f"{owner}#{reference_uid[:8]}"
                        for owner, reference_uid in inbound
                    )
                    raise DedupConflictError(
                        "Dedun cannot absorb Memories with inbound references in "
                        f"version 1: {locations}."
                    )
                for uid in absorbed_uids:
                    if not isinstance(current.memories.get(uid), Memory):
                        raise DedupConflictError(
                            f"Dedun Memory '{uid[:8]}' is no longer directly owned."
                        )
                    current.remove(uid)
                checkpoint = access.store._save_command_locked(  # noqa: SLF001
                    current,
                    AutoCheckpoint(
                        command="dedun",
                        args={
                            "contract": DEDUP_CONTRACT_VERSION,
                            "revision": plan.revision,
                            "selections": [
                                {
                                    "component_uid": selection.component_uid,
                                    "survivor_uid": selection.survivor_uid,
                                }
                                for selection in selections
                            ],
                            "redundancy_evidence_uids": [
                                handoff.uid for handoff in plan.request.handoffs
                            ],
                            **grant_checkpoint_args(access),
                        },
                        description=(
                            f"Resolved {len(plan.components)} semantic redundancy "
                            f"group(s); absorbed {len(absorbed_uids)} Memory item(s)"
                        ),
                    ),
                    expected_context_digest=plan.context_digest,
                )
                if checkpoint is None:
                    raise DedupError(
                        "Dedun Apply produced no checkpoint for a nonempty plan."
                    )
        return DedupReceipt(
            context_uid=plan.context_uid,
            context_name=plan.display_name,
            revision=plan.revision,
            checkpoint_uid=checkpoint.uid,
            selections=selections,
            survivor_uids=survivor_uids,
            absorbed_uids=absorbed_uids,
        )


__all__ = ["MemoryStoreDedupPort"]
