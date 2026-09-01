"""MemoryStore authority and atomic direct or lexical-scope Dedun Apply."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.application.authorization.context_operation import (
    authorized_context_mutation,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    freeze_granted_context_binding,
    grant_checkpoint_args,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
)
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingSource,
)
from memcommit.application.capabilities.memory_issue_analysis.redundancy_scope import (
    RedundancyScopeAnalysis,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.core.context import AutoCheckpoint, Memory, MemoryRef
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.operations.dedun.application import (
    DEDUN_ELIGIBLE_RELATIONS,
    DedunAuthorityError,
    DedunConflictError,
    DedunError,
    DedunProjection,
    DedunReceipt,
    DedunRequest,
    FrozenDedunPlan,
    dedun_projection_record,
    prepare_dedun,
    project_dedun,
    recommended_dedun_selections,
)
from memcommit.application.operations.dedun.analysis import freeze_dedun_analysis
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    find_exact_duplicate_groups,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.application.operations.review.model import direct_context_digest
from memcommit.persistence.store import MemoryStore, context_record_digest


@dataclass
class MemoryStoreDedunPort:
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

    def _access(self, request: DedunRequest) -> ContextAccess:
        source = request.source
        if not self.allow_grants and not self.active_store.context_exists(
            source.display_name
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
            {"READ", "DELETE"} - set(access.view.grant.permissions)
        )
        if missing:
            raise DedunAuthorityError(
                "Dedun Grant lacks required authority: " + ", ".join(missing)
            )

    def freeze(self, request: DedunRequest) -> FrozenDedunPlan:
        if not isinstance(request, DedunRequest):
            raise TypeError("Dedun freeze requires a typed request.")
        access = self._access(request)
        self._require_grant_permissions(access)
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
            item for item in context.iter_items() if isinstance(item, Memory)
        )
        exact_item_groups = (
            tuple(
                group
                for group in find_exact_duplicate_groups(context)
                if group.item_kind != "MEMORY"
            )
            if request.exact_source is not None
            else ()
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
            exact_item_groups=exact_item_groups,
            granted_binding=(
                freeze_granted_context_binding(access)
                if access.view is not None
                else None
            ),
        )

    def _revalidated_access(self, plan: FrozenDedunPlan) -> ContextAccess:
        if plan.granted_binding is not None:
            try:
                access = revalidate_granted_context_binding(
                    plan.granted_binding,
                    required_permission="READ",
                    active_store=self.active_store,
                    registry=self.registry,
                )
            except Exception as error:
                raise DedunAuthorityError(str(error)) from error
            self._require_grant_permissions(access)
            return access
        if not self.active_store.context_exists(plan.context_name):
            raise DedunConflictError(
                f"Dedun Context '{plan.context_name}' no longer exists."
            )
        return ContextAccess(
            store=self.active_store,
            context_name=plan.context_name,
            access_name=plan.display_name,
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
        plan: FrozenDedunPlan,
        projection: DedunProjection,
    ) -> DedunReceipt:
        if not isinstance(plan, FrozenDedunPlan) or not isinstance(
            projection,
            DedunProjection,
        ):
            raise TypeError("Dedun Apply requires a frozen plan and projection.")
        selections = projection.selections
        semantic_member_uids = {
            member.uid for component in plan.components for member in component.members
        }
        semantic_absorbed_uids = tuple(
            uid
            for uid in projection.absorbed_uids
            if uid in semantic_member_uids
        )
        memory_exact_absorbed_uids = {
            uid
            for group in plan.exact_item_groups
            if group.item_kind == "MEMORY"
            for uid in group.absorbed_uids
        }
        survivor_uids = projection.survivor_uids
        absorbed_uids = projection.absorbed_uids
        access = self._revalidated_access(plan)
        with authorized_context_mutation(
            access,
            required_permissions=("READ", "DELETE"),
        ):
            # Scan and mutation share the command lock so a new inbound pointer
            # cannot appear between reference validation and deletion.
            with access.store._command_write_lock():  # noqa: SLF001
                current = access.store.load_for_update(access.context_name)
                if (
                    current.uid != plan.context_uid
                    or context_record_digest(current) != plan.context_digest
                ):
                    raise DedunConflictError(
                        "The Dedun Source changed before Apply; nothing was written."
                    )
                inbound = self._inbound_references(
                    access.store,
                    context_uid=plan.context_uid,
                    absorbed_uids={
                        *semantic_absorbed_uids,
                        *memory_exact_absorbed_uids,
                    },
                )
                if inbound:
                    locations = ", ".join(
                        f"{owner}#{reference_uid[:8]}"
                        for owner, reference_uid in inbound
                    )
                    raise DedunConflictError(
                        "Dedun cannot absorb Memories with inbound references in "
                        f"version 1: {locations}."
                    )
                for uid in semantic_absorbed_uids:
                    if not isinstance(current.memories.get(uid), Memory):
                        raise DedunConflictError(
                            f"Dedun Memory '{uid[:8]}' is no longer directly owned."
                        )
                for uid in absorbed_uids:
                    current.remove(uid)
                checkpoint = access.store._save_command_locked(  # noqa: SLF001
                    current,
                    AutoCheckpoint(
                        command="dedun",
                        args={
                            **dedun_projection_record(plan, projection),
                            **grant_checkpoint_args(access),
                        },
                        description=(
                            "Resolved "
                            f"{len(plan.components) + len(plan.exact_item_groups)} "
                            "redundancy group(s); absorbed "
                            f"{len(absorbed_uids)} direct item(s)"
                        ),
                    ),
                    expected_context_digest=plan.context_digest,
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
            exact_item_groups=plan.exact_item_groups,
        )


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
    plan: FrozenDedunPlan | None
    projection: DedunProjection | None


@dataclass(frozen=True)
class PreparedRecursiveDedunScope:
    """Every per-Context effect prepared before the first Store write."""

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
    """Freeze one local lexical subtree and reject authority crossings."""

    if not isinstance(active_store, MemoryStore) or not isinstance(
        access, ContextAccess
    ):
        raise TypeError("Recursive Dedun requires a Store and Context access.")
    if access.is_granted:
        raise DedunError(
            "Recursive Dedun cannot start from a granted Context; dedun that "
            "Context directly."
        )
    readable = ReadableContextCatalog(
        active_store,
        access,
        registry=registry,
        include_query_routes=False,
    )
    granted_descendants = readable.granted_names_below(access.access_name)
    if granted_descendants:
        raise DedunError(
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
        target_names=(access.access_name,),
        selection_mode="SINGLE",
        include_descendants=True,
    )
    return FrozenRecursiveDedunScope(
        root_name=access.access_name,
        source=source,
        context_catalog=catalog,
    )


def prepare_recursive_dedun_scope(
    frozen: FrozenRecursiveDedunScope,
    analysis: RedundancyScopeAnalysis,
    *,
    port: MemoryStoreDedunPort,
) -> PreparedRecursiveDedunScope:
    """Analyze every Context effect before recursive publication."""

    if not isinstance(frozen, FrozenRecursiveDedunScope) or not isinstance(
        analysis, RedundancyScopeAnalysis
    ):
        raise TypeError("Recursive Dedun preparation requires frozen analysis.")
    if analysis.source.digest != frozen.source.digest:
        raise DedunConflictError("Recursive Dedun analysis does not match its scope.")
    contexts: list[PreparedDedunContext] = []
    for frame in analysis.contexts:
        eligible = tuple(
            handoff
            for handoff in frame.handoffs
            if handoff.classification in DEDUN_ELIGIBLE_RELATIONS
        )
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
        request = DedunRequest(
            eligible,
            exact_source=QualityFindingSource(
                context_uid=context.uid,
                display_name=frame.context_name,
                direct_memory_digest=frame.source.context_digests[0],
            ),
            exact_source_frame_digest=frame.source.digest,
        )
        plan = prepare_dedun(request, port=port)
        projection = project_dedun(plan, recommended_dedun_selections(plan))
        contexts.append(
            PreparedDedunContext(
                context_name=frame.context_name,
                context_uid=context.uid,
                group_count=frame.report.group_count,
                plan=plan,
                projection=projection,
            )
        )
    return PreparedRecursiveDedunScope(frozen=frozen, contexts=tuple(contexts))


def _memory_absorptions(
    plan: FrozenDedunPlan,
    projection: DedunProjection,
) -> set[str]:
    semantic_members = {
        member.uid for component in plan.components for member in component.members
    }
    return {uid for uid in projection.absorbed_uids if uid in semantic_members} | {
        uid
        for group in plan.exact_item_groups
        if group.item_kind == "MEMORY"
        for uid in group.absorbed_uids
    }


def apply_recursive_dedun_scope(
    active_store: MemoryStore,
    prepared: PreparedRecursiveDedunScope,
) -> DedunScopeReceipt:
    """Publish all analyzed local effects in one rollback-safe batch."""

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
        raise DedunConflictError(
            "The Context namespace changed during recursive Dedun; nothing was written."
        )
    graph = tuple(active_store.load_direct_context_graph_strict())
    graph_digests = {context.name: context_record_digest(context) for context in graph}
    applications: list[
        tuple[PreparedDedunContext, FrozenDedunPlan, DedunProjection]
    ] = []
    for frame in changed:
        assert frame.plan is not None and frame.projection is not None
        plan = frame.plan
        projection = frame.projection
        if plan.granted_binding is not None or plan.context_name != frame.context_name:
            raise DedunError("Recursive Dedun accepts only local Context plans.")
        current = active_store.load_for_update(plan.context_name)
        if (
            current.uid != plan.context_uid
            or context_record_digest(current) != plan.context_digest
        ):
            raise DedunConflictError(
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
        raise DedunConflictError(
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
        len(projection.absorbed_uids) for _frame, _plan, projection in applications
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
            member.uid for component in plan.components for member in component.members
        }
        for uid in projection.absorbed_uids:
            if uid in semantic_members and not isinstance(
                current.memories.get(uid), Memory
            ):
                raise DedunConflictError(
                    f"Dedun Memory '{uid[:8]}' is no longer directly owned."
                )
            current.remove(uid)
        entries.append(
            (
                current,
                AutoCheckpoint(
                    command="dedun",
                    args={
                        **dedun_projection_record(plan, projection),
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
        access_name=prepared.frozen.root_name,
        permission="READ",
    )
    with authorized_context_mutation(
        root_access,
        required_permissions=("READ", "DELETE"),
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
    "DedunScopeReceipt",
    "FrozenRecursiveDedunScope",
    "MemoryStoreDedunPort",
    "PreparedDedunContext",
    "PreparedRecursiveDedunScope",
    "apply_recursive_dedun_scope",
    "freeze_recursive_dedun_scope",
    "prepare_recursive_dedun_scope",
]
