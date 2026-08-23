"""Atomic local lexical-scope application for immediate Dedun."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.authority.access import ContextAccess, authorized_context_mutation
from memcommit.context import AutoCheckpoint, Memory, MemoryRef
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.readable_catalog import ReadableContextCatalog
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.dedup_application import (
    DEDUP_CONTRACT_VERSION,
    DEDUP_ELIGIBLE_RELATIONS,
    DedupConflictError,
    DedupError,
    DedupRequest,
    DedupSelection,
    FrozenDedupPlan,
    prepare_dedup,
    recommended_dedup_selections,
    validate_dedup_selections,
)
from memcommit.dedup_runtime import MemoryStoreDedupPort
from memcommit.profile_config import ProfileRegistry
from memcommit.quality_find_workbench import QualityFindSourceFrame
from memcommit.quality_finding_handoff import QualityFindingSource
from memcommit.redundancy_scope import RedundancyScopeAnalysis
from memcommit.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class FrozenRecursiveDedunScope:
    """One local subtree frozen before its semantic provider turns."""

    root_name: str
    source: QualityFindSourceFrame
    context_catalog: tuple[str, ...]


@dataclass(frozen=True)
class PreparedDedunContext:
    """One independently analyzed Context and its optional nonempty effect."""

    context_name: str
    context_uid: str
    group_count: int
    plan: FrozenDedupPlan | None
    projection: "DedunScopeProjection | None"


@dataclass(frozen=True)
class DedunScopeProjection:
    """One validated provider-free survivor effect before batch publication."""

    selections: tuple[DedupSelection, ...]
    survivor_uids: tuple[str, ...]
    absorbed_uids: tuple[str, ...]


@dataclass(frozen=True)
class PreparedRecursiveDedunScope:
    """Every per-Context decision prepared before the first Store write."""

    frozen: FrozenRecursiveDedunScope
    contexts: tuple[PreparedDedunContext, ...]


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


def freeze_recursive_dedun_scope(
    active_store: MemoryStore,
    access: ContextAccess,
    *,
    registry: ProfileRegistry | None = None,
) -> FrozenRecursiveDedunScope:
    """Freeze a local lexical subtree and reject authority-domain crossings."""

    if not isinstance(active_store, MemoryStore) or not isinstance(
        access, ContextAccess
    ):
        raise TypeError("Recursive Dedun requires a Store and Context access.")
    if access.is_granted:
        raise DedupError(
            "Recursive Dedun cannot start from a granted Context; dedun that "
            "Context directly."
        )
    readable = ReadableContextCatalog(
        active_store,
        access,
        registry=registry,
        include_query_routes=False,
    )
    granted_descendants = readable.granted_names_below(access.display_name)
    if granted_descendants:
        raise DedupError(
            "Recursive Dedun cannot cross granted Context boundaries: "
            + ", ".join(repr(name) for name in granted_descendants)
            + ". Dedun those Contexts directly."
        )

    catalog = tuple(access.store.list_context_names())
    names = expand_lexical_context_names(
        ContextScope.create((access.context_name,), include_descendants=True),
        catalog,
    )
    source = QualityFindSourceFrame.create(
        tuple(access.store.load_direct(name) for name in names),
        context_names=names,
        target_names=(access.display_name,),
        selection_mode="SINGLE",
        include_descendants=True,
    )
    return FrozenRecursiveDedunScope(
        root_name=access.display_name,
        source=source,
        context_catalog=catalog,
    )


def prepare_recursive_dedun_scope(
    frozen: FrozenRecursiveDedunScope,
    analysis: RedundancyScopeAnalysis,
    *,
    port: MemoryStoreDedupPort,
) -> PreparedRecursiveDedunScope:
    """Prepare every deterministic survivor effect before publication."""

    if not isinstance(frozen, FrozenRecursiveDedunScope) or not isinstance(
        analysis, RedundancyScopeAnalysis
    ):
        raise TypeError("Recursive Dedun preparation requires frozen analysis.")
    if analysis.source.digest != frozen.source.digest:
        raise DedupConflictError("Recursive Dedun analysis does not match its scope.")
    contexts: list[PreparedDedunContext] = []
    for frame in analysis.contexts:
        eligible = tuple(
            handoff
            for handoff in frame.handoffs
            if handoff.classification in DEDUP_ELIGIBLE_RELATIONS
        )
        group_count = frame.report.group_count
        context = frame.source.contexts[0]
        if not eligible and not frame.report.exact_item_groups:
            contexts.append(
                PreparedDedunContext(
                    context_name=frame.context_name,
                    context_uid=context.uid,
                    group_count=0,
                    plan=None,
                    projection=None,
                )
            )
            continue
        request = DedupRequest(
            eligible,
            exact_source=QualityFindingSource(
                context_uid=context.uid,
                display_name=frame.context_name,
                direct_memory_digest=frame.source.context_digests[0],
            ),
            exact_source_frame_digest=frame.source.digest,
        )
        plan = prepare_dedup(request, port=port)
        projection = _project_dedun_scope_effect(
            plan,
            recommended_dedup_selections(plan),
        )
        contexts.append(
            PreparedDedunContext(
                context_name=frame.context_name,
                context_uid=context.uid,
                group_count=group_count,
                plan=plan,
                projection=projection,
            )
        )
    return PreparedRecursiveDedunScope(frozen=frozen, contexts=tuple(contexts))


def _project_dedun_scope_effect(
    plan: FrozenDedupPlan,
    selections: tuple[DedupSelection, ...],
) -> DedunScopeProjection:
    """Validate the complete survivor set without entering the direct port."""

    exact = validate_dedup_selections(plan, selections)
    semantic_survivors = tuple(selection.survivor_uid for selection in exact)
    semantic_absorbed = tuple(
        member.uid
        for component, selection in zip(plan.components, exact, strict=True)
        for member in component.members
        if member.uid != selection.survivor_uid
    )
    exact_survivors = tuple(
        group.survivor_uid for group in plan.exact_item_groups
    )
    exact_absorbed = tuple(
        uid for group in plan.exact_item_groups for uid in group.absorbed_uids
    )
    absorbed = semantic_absorbed + exact_absorbed
    if not absorbed:
        raise DedupError("Recursive Dedun requires a nonempty direct-item effect.")
    return DedunScopeProjection(
        selections=exact,
        survivor_uids=semantic_survivors + exact_survivors,
        absorbed_uids=absorbed,
    )


def _dedun_scope_record(
    plan: FrozenDedupPlan,
    projection: DedunScopeProjection,
) -> dict[str, object]:
    """Retain the same immutable per-Context Review evidence as direct Dedun."""

    return {
        "contract": DEDUP_CONTRACT_VERSION,
        "revision": plan.revision,
        "selections": [
            {
                "component_uid": selection.component_uid,
                "survivor_uid": selection.survivor_uid,
            }
            for selection in projection.selections
        ],
        "components": [
            {
                "component_uid": component.uid,
                "survivor_uid": selection.survivor_uid,
                "members": [
                    {
                        "uid": member.uid,
                        "content": member.content,
                        "ordinal": member.ordinal,
                        "selected": member.uid == selection.survivor_uid,
                    }
                    for member in component.members
                ],
                "evidence": [
                    {
                        "finding_uid": evidence.finding_uid,
                        "handoff_uid": evidence.handoff_uid,
                        "left_uid": evidence.left_uid,
                        "right_uid": evidence.right_uid,
                        "relation": evidence.relation,
                        "reason": evidence.reason,
                    }
                    for evidence in component.evidence
                ],
            }
            for component, selection in zip(
                plan.components,
                projection.selections,
                strict=True,
            )
        ],
        "exact_item_groups": [
            {
                "item_kind": group.item_kind,
                "survivor_uid": group.survivor_uid,
                "absorbed_uids": list(group.absorbed_uids),
                "summary": group.summary,
            }
            for group in plan.exact_item_groups
        ],
        "redundancy_evidence_uids": [
            handoff.uid for handoff in plan.request.handoffs
        ],
        "survivor_uids": list(projection.survivor_uids),
        "absorbed_uids": list(projection.absorbed_uids),
    }


def _memory_absorptions(
    plan: FrozenDedupPlan,
    projection: DedunScopeProjection,
) -> set[str]:
    semantic_members = {
        member.uid for component in plan.components for member in component.members
    }
    return {
        uid for uid in projection.absorbed_uids if uid in semantic_members
    } | {
        uid
        for group in plan.exact_item_groups
        if group.item_kind == "MEMORY"
        for uid in group.absorbed_uids
    }


def apply_recursive_dedun_scope(
    active_store: MemoryStore,
    prepared: PreparedRecursiveDedunScope,
) -> DedunScopeReceipt:
    """Publish all prepared local effects in one rollback-safe command batch."""

    if not isinstance(active_store, MemoryStore) or not isinstance(
        prepared, PreparedRecursiveDedunScope
    ):
        raise TypeError("Recursive Dedun Apply requires a Store and prepared scope.")
    changed = tuple(frame for frame in prepared.contexts if frame.plan is not None)
    if not changed:
        return DedunScopeReceipt(
            root_name=prepared.frozen.root_name,
            contexts=tuple(
                DedunScopeContextReceipt(
                    context_name=frame.context_name,
                    context_uid=frame.context_uid,
                    group_count=0,
                    checkpoint_uid=None,
                    survivor_uids=(),
                    absorbed_uids=(),
                )
                for frame in prepared.contexts
            ),
            operation_uid=None,
        )

    if tuple(active_store.list_context_names()) != prepared.frozen.context_catalog:
        raise DedupConflictError(
            "The Context namespace changed during recursive Dedun; nothing was written."
        )
    graph = tuple(active_store.load_direct_context_graph_strict())
    graph_digests = {
        context.name: context_record_digest(context) for context in graph
    }
    applications: list[
        tuple[PreparedDedunContext, FrozenDedupPlan, DedunScopeProjection]
    ] = []
    for frame in changed:
        assert frame.plan is not None and frame.projection is not None
        plan = frame.plan
        projection = frame.projection
        if plan.granted_binding is not None or plan.context_name != frame.context_name:
            raise DedupError("Recursive Dedun accepts only local Context plans.")
        current = active_store.load_for_update(plan.context_name)
        if (
            current.uid != plan.context_uid
            or context_record_digest(current) != plan.context_digest
        ):
            raise DedupConflictError(
                f"Dedun Context '{plan.display_name}' changed; nothing was written."
            )
        applications.append((frame, plan, projection))

    absorbed_by_context_uid = {
        plan.context_uid: _memory_absorptions(plan, projection)
        for _frame, plan, projection in applications
    }
    inbound = tuple(
        (owner.name, item.uid)
        for owner in graph
        for item in owner.iter_items()
        if isinstance(item, MemoryRef)
        and item.target_memory_uid
        in absorbed_by_context_uid.get(item.target_context_uid, set())
    )
    if inbound:
        locations = ", ".join(
            f"{owner}#{reference_uid[:8]}" for owner, reference_uid in inbound
        )
        raise DedupConflictError(
            "Recursive Dedun cannot absorb Memories with inbound references in "
            f"version 1: {locations}."
        )

    operation_uid = str(uuid.uuid4())
    membership = [
        {"uid": plan.context_uid, "name": plan.context_name}
        for _frame, plan, _projection in applications
    ]
    tree_receipt = {
        "version": 1,
        "operation_uid": operation_uid,
        "root": prepared.frozen.root_name,
        "include_descendants": True,
    }
    total_absorbed = sum(
        len(projection.absorbed_uids)
        for _frame, _plan, projection in applications
    )
    description = (
        f"Resolved recursive Dedun across {len(applications)} Context(s); "
        f"absorbed {total_absorbed} direct item(s)"
    )
    entries = []
    changed_names: set[str] = set()
    for _frame, plan, projection in applications:
        changed_names.add(plan.context_name)
        current = active_store.load_for_update(plan.context_name)
        semantic_members = {
            member.uid
            for component in plan.components
            for member in component.members
        }
        for uid in projection.absorbed_uids:
            if uid in semantic_members and not isinstance(
                current.memories.get(uid), Memory
            ):
                raise DedupConflictError(
                    f"Dedun Memory '{uid[:8]}' is no longer directly owned."
                )
            current.remove(uid)
        entries.append(
            (
                current,
                AutoCheckpoint(
                    command="dedun",
                    args={
                        **_dedun_scope_record(plan, projection),
                        "dedun_tree": tree_receipt,
                        "command_contexts": membership,
                    },
                    description=description,
                ),
                plan.context_digest,
            )
        )

    unchanged_bindings = tuple(
        (context.name, context.uid, graph_digests[context.name])
        for context in graph
        if context.name not in changed_names
    )
    root_access = ContextAccess(
        store=active_store,
        context_name=prepared.frozen.root_name,
        display_name=prepared.frozen.root_name,
        attachment_name=None,
        permission="READ",
    )
    with authorized_context_mutation(
        root_access,
        required_permissions=("READ", "DERIVE", "DELETE"),
    ):
        checkpoints = active_store.save_context_command_batch(
            entries,
            source_bindings=unchanged_bindings,
            expected_context_catalog=prepared.frozen.context_catalog,
        )
    checkpoint_by_name = {
        context.name: checkpoint.uid
        for (context, _checkpoint, _digest), checkpoint in zip(
            entries,
            checkpoints,
            strict=True,
        )
    }
    effects = {
        frame.context_name: (plan, projection)
        for frame, plan, projection in applications
    }
    return DedunScopeReceipt(
        root_name=prepared.frozen.root_name,
        contexts=tuple(
            DedunScopeContextReceipt(
                context_name=frame.context_name,
                context_uid=frame.context_uid,
                group_count=frame.group_count,
                checkpoint_uid=checkpoint_by_name.get(frame.context_name),
                survivor_uids=(
                    effects[frame.context_name][1].survivor_uids
                    if frame.context_name in effects
                    else ()
                ),
                absorbed_uids=(
                    effects[frame.context_name][1].absorbed_uids
                    if frame.context_name in effects
                    else ()
                ),
            )
            for frame in prepared.contexts
        ),
        operation_uid=operation_uid,
    )


__all__ = [
    "DedunScopeContextReceipt",
    "DedunScopeProjection",
    "DedunScopeReceipt",
    "FrozenRecursiveDedunScope",
    "PreparedDedunContext",
    "PreparedRecursiveDedunScope",
    "apply_recursive_dedun_scope",
    "freeze_recursive_dedun_scope",
    "prepare_recursive_dedun_scope",
]
