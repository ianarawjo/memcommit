"""MemoryStore authority, freshness, and Apply boundary for Resolve."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    authorized_context_mutation,
    freeze_granted_context_binding,
    grant_checkpoint_args,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.context_locator import resolve_context_locator
from memcommit.profile_config import ProfileRegistry
from memcommit.operations.resolve.application import (
    RESOLVE_CONTRACT_VERSION,
    FrozenResolveFrame,
    ResolveAuthorityError,
    ResolveCandidate,
    ResolveConflictError,
    ResolveEffectKind,
    ResolveError,
    ResolveFrameMemory,
    ResolveReceipt,
    ResolveRequest,
)
from memcommit.resolve_rules import RESOLVE_RULESET_VERSION
from memcommit.store import MemoryStore, context_record_digest


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
        "ruleset": RESOLVE_RULESET_VERSION,
        "context": {
            "uid": context_uid,
            "name": context_name,
            "display_name": display_name,
            "digest": context_digest,
        },
        "actionable_uids": list(actionable_uids),
        "requested_effects": list(request.requested_effects),
        "guidance": request.guidance,
        "target_fit": request.target_fit,
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
            ).load_direct(access.display_name)
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
            missing_authority = () if "DERIVE" in grant_permissions else ("DERIVE",)
            binding = freeze_granted_context_binding(access)
        digest = context_record_digest(authority)
        return FrozenResolveFrame(
            request=request,
            context_uid=authority.uid,
            context_name=authority.name,
            display_name=access.display_name,
            context_digest=digest,
            revision=_revision(
                request,
                context_uid=authority.uid,
                context_name=authority.name,
                display_name=access.display_name,
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
            display_name=frame.display_name,
            attachment_name=None,
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
            required = {"READ", "DERIVE", *frame.allowed_effects}
            missing = tuple(sorted(required - permissions))
            if missing:
                raise ResolveAuthorityError(
                    "Resolve Grant lost required authority: " + ", ".join(missing)
                )
        self._require_current(frame, access)

    @staticmethod
    def _required_permissions(candidate: ResolveCandidate) -> tuple[str, ...]:
        effects = {effect.kind for effect in candidate.effects}
        return (
            "READ",
            "DERIVE",
            *(effect for effect in _EFFECT_PERMISSION_ORDER if effect in effects),
        )

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

    def apply(
        self,
        frame: FrozenResolveFrame,
        candidate: ResolveCandidate,
    ) -> ResolveReceipt:
        if not isinstance(frame, FrozenResolveFrame) or not isinstance(
            candidate, ResolveCandidate
        ):
            raise TypeError("Resolve Apply requires a reviewed frame and candidate.")
        if any(
            effect.kind not in frame.allowed_effects for effect in candidate.effects
        ):
            raise ResolveAuthorityError(
                "Resolve candidate exceeds the reviewed effect capabilities."
            )
        if any(
            effect.owner_context_uid != frame.context_uid
            or effect.owner_context_name != frame.context_name
            for effect in candidate.effects
        ):
            raise ResolveConflictError(
                "Resolve candidate names an owner outside its reviewed Context."
            )
        access = self._revalidated_access(frame)
        required_permissions = self._required_permissions(candidate)
        deleted_uids = {
            effect.memory_uid for effect in candidate.effects if effect.kind == "DELETE"
        }
        with authorized_context_mutation(
            access,
            required_permissions=required_permissions,
        ):
            # The command lock makes the inbound-reference scan, Context CAS,
            # and checkpoint one ordered command. A concurrent writer cannot
            # insert a new pointer between the scan and the deletion.
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
                        "Resolve cannot delete Memories with inbound references "
                        f"in version 1: {locations}."
                    )
                for effect in candidate.effects:
                    current_item = current.memories.get(effect.memory_uid)
                    if effect.kind == "CREATE":
                        if current_item is not None:
                            raise ResolveConflictError(
                                "Resolve CREATE uid already exists in the target."
                            )
                        assert effect.new_content is not None
                        current.add(Memory(effect.memory_uid, effect.new_content))
                    elif effect.kind == "UPDATE":
                        if (
                            not isinstance(current_item, Memory)
                            or current_item.content != effect.old_content
                        ):
                            raise ResolveConflictError(
                                "Resolve UPDATE target no longer matches its pre-image."
                            )
                        assert effect.new_content is not None
                        current.replace(Memory(effect.memory_uid, effect.new_content))
                    else:
                        if (
                            not isinstance(current_item, Memory)
                            or current_item.content != effect.old_content
                        ):
                            raise ResolveConflictError(
                                "Resolve DELETE target no longer matches its pre-image."
                            )
                        current.remove(effect.memory_uid)
                checkpoint = access.store._save_command_locked(  # noqa: SLF001
                    current,
                    AutoCheckpoint(
                        command="resolve",
                        args={
                            "contract": RESOLVE_CONTRACT_VERSION,
                            "ruleset": RESOLVE_RULESET_VERSION,
                            "revision": frame.revision,
                            "target_fit": frame.request.target_fit,
                            "candidate_uid": candidate.uid,
                            "candidate_summary": candidate.summary,
                            "classification": candidate.classification,
                            "resolution_level": candidate.resolution_level,
                            "rule_ids": list(candidate.rule_ids),
                            "grounded": candidate.grounded,
                            "verification_reason": candidate.verification_reason,
                            "issues": [
                                {
                                    "uid": issue.uid,
                                    "kind": issue.kind,
                                    "memory_uids": list(issue.memory_uids),
                                    "selected_interpretation": (
                                        issue.selected_interpretation
                                    ),
                                    "basis_memory_uids": list(issue.basis_memory_uids),
                                    "assumptions": list(issue.assumptions),
                                    "reason": issue.reason,
                                }
                                for issue in candidate.issues
                            ],
                            "fit": {
                                "question_id": candidate.fit.question_id,
                                "verdict": candidate.fit.verdict,
                                "reason": candidate.fit.reason,
                                "considered_proposition_ids": list(
                                    candidate.fit.considered_proposition_ids
                                ),
                                "material_proposition_ids": list(
                                    candidate.fit.material_proposition_ids
                                ),
                            },
                            "effects": [
                                effect.canonical_value() for effect in candidate.effects
                            ],
                            "guidance": frame.request.guidance,
                            **grant_checkpoint_args(access),
                        },
                        description=(
                            f"Resolved {len(candidate.effects)} Memory effect(s) "
                            f"with candidate [{candidate.uid[-8:]}]"
                        ),
                    ),
                    expected_context_digest=frame.context_digest,
                )
                if checkpoint is None:
                    raise ResolveError(
                        "Resolve Apply produced no checkpoint for a nonempty plan."
                    )
        return ResolveReceipt(
            context_uid=frame.context_uid,
            context_name=frame.display_name,
            revision=frame.revision,
            candidate_uid=candidate.uid,
            checkpoint_uid=checkpoint.uid,
            created_uids=tuple(
                effect.memory_uid
                for effect in candidate.effects
                if effect.kind == "CREATE"
            ),
            updated_uids=tuple(
                effect.memory_uid
                for effect in candidate.effects
                if effect.kind == "UPDATE"
            ),
            deleted_uids=tuple(
                effect.memory_uid
                for effect in candidate.effects
                if effect.kind == "DELETE"
            ),
        )


__all__ = ["MemoryStoreResolvePort"]
