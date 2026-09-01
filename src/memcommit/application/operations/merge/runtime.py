"""MemoryStore and Grant infrastructure adapter for structural Merge."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.application.authorization.context_operation import (
    authorized_context_operation,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.core.context import (
    AutoCheckpoint,
    Context,
    Memory,
)
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.context_access.granted_context_navigation import (
    freeze_granted_context_navigation,
)
from memcommit.application.operations.merge.application import (
    FrozenMergePlan,
    MergeAddition,
    MergeConflict,
    MergeContextResult,
    MergeDecision,
    MergeItemKind,
    MergePort,
    MergeReach,
    MergeRequest,
    MergeResolution,
    MergeResult,
    run_merge,
)
from memcommit.application.operations.merge.planning import (
    PlannedContextMerge,
    materialize_context_merge,
    plan_context_merge,
    resolution_map,
)
from memcommit.application.operations.merge.tree import (
    align_context_names,
    fresh_target_contexts,
    project_context_for_tree_merge,
)
from memcommit.application.operations.merge.tree_persistence import MergeTreeWrite, commit_merge_tree
from memcommit.application.capabilities.history.reconstruction.memory_lineage_relations import (
    MemoryLineageEdge,
    checkpoint_memory_lineage_edges,
    memory_content_sha256,
    memory_lineage_record,
    resolve_lineage_target_uids,
)
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.persistence.store.infrastructure.write_protection import WriteProtectionError


def _memory_only_source(source: Context) -> Context:
    """Copy portable Memory values without carrying cross-Profile pointers."""

    result = Context(uid=source.uid, name=source.name)
    for item in source.iter_items():
        if isinstance(item, Memory):
            result.add(Memory(uid=item.uid, content=item.content))
    return result


def _merge_decision_checkpoint_record(
    conflicts: tuple[MergeConflict, ...],
    resolutions: tuple[MergeResolution, ...],
) -> dict[str, object]:
    """Retain exact reviewed choices without duplicating Memory bodies."""

    resolution_by_uid = {
        resolution.conflict_uid: resolution.decision.value
        for resolution in resolutions
    }
    return {
        "version": 1,
        "decisions": [
            {
                "conflict_uid": conflict.uid,
                "kind": conflict.kind.value,
                "decision": resolution_by_uid[conflict.uid],
                "source_name": conflict.source_name,
                "target_name": conflict.target_name,
                "source_uid": conflict.source.uid,
                "target_uids": [target.uid for target in conflict.targets],
            }
            for conflict in conflicts
            if conflict.uid in resolution_by_uid
        ],
    }


def _merge_checkpoint_description(
    *,
    source_name: str,
    target_name: str,
    additions: tuple[MergeAddition, ...],
    unchanged_count: int,
    conflicts: tuple[MergeConflict, ...],
    resolutions: tuple[MergeResolution, ...],
    recursive: bool = False,
) -> str:
    relevant = {conflict.uid for conflict in conflicts}
    take_count = sum(
        resolution.conflict_uid in relevant
        and resolution.decision is MergeDecision.TAKE_SOURCE
        for resolution in resolutions
    )
    keep_count = sum(
        resolution.conflict_uid in relevant
        and resolution.decision is MergeDecision.KEEP_TARGET
        for resolution in resolutions
    )
    prefix = "Recursively merged" if recursive else "Merged"
    return (
        f"{prefix} '{source_name}' into '{target_name}': "
        f"new {len(additions)}; already present {unchanged_count}; "
        f"kept Target {keep_count}; took Source {take_count}"
    )


def _take_source_allowed(access: ContextAccess) -> bool:
    """Do not advertise replacement when a granted Target lacks UPDATE."""

    return access.view is None or "UPDATE" in access.view.grant.permissions


def _target_plan_protection(
    access: ContextAccess,
    target: Context,
) -> tuple[bool, frozenset[str]]:
    """Freeze the Target policy that determines reviewable replacements."""

    state = access.store.write_protection_state()
    if state.profile_is_protected():
        raise WriteProtectionError(
            "Profile is locked against writes. Unlock that Profile first."
        )
    return (
        not state.context_is_protected(target.uid),
        state.protected_memory_uids(target.uid),
    )


def _require_planned_additions_mutable(
    *,
    target: Context,
    context_plan: PlannedContextMerge,
    target_context_mutable: bool,
) -> None:
    """Reject a review whose unconditional additions cannot be applied."""

    if context_plan.additions and not target_context_mutable:
        raise WriteProtectionError(
            f"Context '{target.name}' is locked against changes. "
            "Unlock that Context first."
        )


@dataclass(frozen=True)
class _StoreMergeToken:
    """Bind a frozen direct plan to its exact authority and candidate state."""

    owner: object
    operation_uid: str
    source_access: ContextAccess
    target_access: ContextAccess
    source: Context
    target: Context
    context_plan: PlannedContextMerge
    source_projection_digest: str


@dataclass(frozen=True)
class _RecursiveSourceFrame:
    access: ContextAccess
    context: Context
    digest: str


@dataclass(frozen=True)
class _RecursiveTargetFrame:
    access: ContextAccess | None
    context: Context
    source: Context
    context_plan: PlannedContextMerge
    expected_digest: str | None
    records_memory_lineage: bool

    @property
    def created(self) -> bool:
        return self.expected_digest is None


def _lineage_target_uids(
    source_access: ContextAccess,
    target_access: ContextAccess,
    source: Context,
    target: Context,
) -> dict[str, str]:
    """Resolve only same-Store ordinary lineage retained by both histories."""

    if (
        source_access.is_granted
        or target_access.is_granted
        or source_access.store.store_dir != target_access.store.store_dir
    ):
        return {}
    edges = checkpoint_memory_lineage_edges(
        (
            source_access.store.list_checkpoints(source_access.context_name),
            target_access.store.list_checkpoints(target_access.context_name),
        )
    )
    return resolve_lineage_target_uids(source, target, edges)


def _merge_memory_lineage_record(
    operation_uid: str,
    source: Context,
    candidate: Context,
    context_plan: PlannedContextMerge,
) -> dict[str, object]:
    """Bind every structural Memory transfer to the exact post-image."""

    edges: list[MemoryLineageEdge] = []
    for mapping in context_plan.memory_mappings:
        source_memory = source.memories.get(mapping.source_uid)
        target_memory = candidate.memories.get(mapping.target_uid)
        if not isinstance(source_memory, Memory) or not isinstance(
            target_memory, Memory
        ):
            raise ValueError("Merge Memory lineage mapping is not materializable.")
        edges.append(
            MemoryLineageEdge(
                source_context_uid=source.uid,
                source_memory_uid=source_memory.uid,
                target_context_uid=candidate.uid,
                target_memory_uid=target_memory.uid,
                source_content_sha256=memory_content_sha256(source_memory.content),
                target_content_sha256=memory_content_sha256(target_memory.content),
            )
        )
    return memory_lineage_record(operation_uid, edges)


@dataclass(frozen=True)
class _RecursiveMergeToken:
    """Bind a whole path-aligned plan to its frozen membership and candidates."""

    owner: object
    operation_uid: str
    source_root_access: ContextAccess
    target_root_access: ContextAccess
    sources: tuple[_RecursiveSourceFrame, ...]
    targets: tuple[_RecursiveTargetFrame, ...]
    expected_source_names: tuple[str, ...]
    expected_target_names: tuple[str, ...]


class MemoryStoreMergePort(MergePort):
    """Plan and commit structural Merge against one current-name snapshot."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreMergePort":
        return cls(store, current_name=store.current_context_name())

    @property
    def store(self) -> MemoryStore:
        """Expose the composed Store only to setup/catalog adapters."""

        return self._store

    @property
    def current_context_name(self) -> str | None:
        """Return the one command-start navigation snapshot."""

        return self._current_name

    def _load_source(self, access: ContextAccess) -> Context:
        if access.is_granted:
            return GrantedReadStore(access).load(access.display_name)
        return access.store.load_for_update(access.context_name)

    @staticmethod
    def _scope_names(root: str, names: tuple[str, ...]) -> tuple[str, ...]:
        return expand_lexical_context_names(
            ContextScope.create((root,), include_descendants=True),
            tuple(sorted(names, key=str.casefold)),
        )

    def _recursive_source_accesses(
        self,
        root: ContextAccess,
    ) -> tuple[ContextAccess, ...]:
        if not root.is_granted:
            names = self._scope_names(
                root.context_name,
                tuple(root.store.list_context_names()),
            )
        else:
            navigation = freeze_granted_context_navigation(self._store)
            names = self._scope_names(
                root.display_name,
                tuple(navigation.readable_names),
            )
        accesses = tuple(
            resolve_context_access(
                self._store,
                name,
                current_name=self._current_name,
                required_permission="READ",
            )
            for name in names
        )
        if not accesses or accesses[0].display_name != root.display_name:
            raise RuntimeError("Recursive Merge lost its Source root.")
        return accesses

    def _recursive_target_accesses(
        self,
        root: ContextAccess,
    ) -> tuple[ContextAccess, ...]:
        if not root.is_granted:
            names = self._scope_names(
                root.context_name,
                tuple(root.store.list_context_names()),
            )
        else:
            navigation = freeze_granted_context_navigation(self._store)
            names = self._scope_names(
                root.display_name,
                tuple(navigation.names),
            )
        accesses = tuple(
            resolve_context_access(
                self._store,
                name,
                current_name=self._current_name,
                required_permission="CREATE",
            )
            for name in names
        )
        if not accesses or accesses[0].display_name != root.display_name:
            raise RuntimeError("Recursive Merge lost its Target root.")
        return accesses

    def freeze(self, request: MergeRequest) -> FrozenMergePlan:
        if request.reach is MergeReach.DESCENDANTS:
            return self._freeze_recursive(request)
        return self._freeze_direct(request)

    def _freeze_direct(self, request: MergeRequest) -> FrozenMergePlan:
        candidates = freeze_profile_context_access_candidates(
            self._store,
            current_name=self._current_name,
        )
        source_access = resolve_existing_context_access(
            self._store,
            request.source_locator,
            current_name=self._current_name,
            required_permission="READ",
            candidates=candidates,
        ).value
        target_access = resolve_existing_context_access(
            self._store,
            request.target_locator,
            current_name=self._current_name,
            required_permission="CREATE",
            candidates=candidates,
        ).value
        source = self._load_source(source_access)
        target = target_access.store.load_for_update(target_access.context_name)
        if (
            target.uid == source.uid
            and source_access.store.store_dir == target_access.store.store_dir
        ):
            raise ValueError("cannot merge a context into itself.")

        cross_profile = source_access.store.store_dir != target_access.store.store_dir
        merge_source = _memory_only_source(source) if cross_profile else source
        source_projection_digest = context_record_digest(source)
        target_digest = target._store_digest or context_record_digest(target)
        target_context_mutable, protected_target_uids = _target_plan_protection(
            target_access,
            target,
        )
        context_plan = plan_context_merge(
            merge_source,
            target,
            source_name=source_access.display_name,
            target_name=target_access.display_name,
            take_source_allowed=_take_source_allowed(target_access),
            target_context_mutable=target_context_mutable,
            protected_target_uids=protected_target_uids,
            lineage_target_uids=_lineage_target_uids(
                source_access,
                target_access,
                merge_source,
                target,
            ),
        )
        _require_planned_additions_mutable(
            target=target,
            context_plan=context_plan,
            target_context_mutable=target_context_mutable,
        )
        context_result = MergeContextResult(
            source_name=source_access.display_name,
            source_uid=source.uid,
            target_name=target_access.display_name,
            target_uid=target.uid,
            target_created=False,
            additions=context_plan.additions,
            unchanged=context_plan.unchanged,
            conflicts=context_plan.conflicts,
        )
        return FrozenMergePlan(
            request=request,
            source_name=source_access.display_name,
            source_uid=source.uid,
            source_digest=source_projection_digest,
            target_name=target_access.display_name,
            target_uid=target.uid,
            target_digest=target_digest,
            additions=context_plan.additions,
            contexts=(context_result,),
            cross_profile_memory_only=cross_profile,
            token=_StoreMergeToken(
                owner=self._owner,
                operation_uid=str(uuid.uuid4()),
                source_access=source_access,
                target_access=target_access,
                source=merge_source,
                target=target,
                context_plan=context_plan,
                source_projection_digest=source_projection_digest,
            ),
            mutates_granted_authority=target_access.is_granted,
            unchanged=context_plan.unchanged,
            conflicts=context_plan.conflicts,
        )

    def _freeze_recursive(self, request: MergeRequest) -> FrozenMergePlan:
        candidates = freeze_profile_context_access_candidates(
            self._store,
            current_name=self._current_name,
        )
        source_root_access = resolve_existing_context_access(
            self._store,
            request.source_locator,
            current_name=self._current_name,
            required_permission="READ",
            candidates=candidates,
        ).value
        target_root_access = resolve_existing_context_access(
            self._store,
            request.target_locator,
            current_name=self._current_name,
            required_permission="CREATE",
            candidates=candidates,
        ).value
        if source_root_access.store.store_dir == target_root_access.store.store_dir:
            source_root = source_root_access.context_name
            target_root = target_root_access.context_name
            if (
                source_root == target_root
                or source_root.startswith(target_root + "/")
                or target_root.startswith(source_root + "/")
            ):
                raise ValueError(
                    "Recursive Merge requires disjoint Source and Target trees."
                )

        source_accesses = self._recursive_source_accesses(source_root_access)
        target_accesses = self._recursive_target_accesses(target_root_access)
        source_frames = tuple(
            _RecursiveSourceFrame(
                access=access,
                context=self._load_source(access),
                digest="",
            )
            for access in source_accesses
        )
        source_frames = tuple(
            _RecursiveSourceFrame(
                access=frame.access,
                context=frame.context,
                digest=context_record_digest(frame.context),
            )
            for frame in source_frames
        )
        target_contexts = {
            access.display_name: access.store.load_for_update(access.context_name)
            for access in target_accesses
        }
        aligned = align_context_names(
            tuple(frame.access.display_name for frame in source_frames),
            source_root=source_root_access.display_name,
            target_root=target_root_access.display_name,
        )
        target_access_by_display = {
            access.display_name: access for access in target_accesses
        }
        canonical_target_names: dict[str, str] = {}
        existing_by_canonical_name: dict[str, Context] = {}
        display_target_name_by_source: dict[str, str] = {}
        for source_name, target_display_name in aligned:
            display_target_name_by_source[source_name] = target_display_name
            target_access = target_access_by_display.get(target_display_name)
            if target_access is None:
                if target_root_access.is_granted:
                    raise ValueError(
                        "Recursive Merge cannot create a missing Context through "
                        "a granted Target."
                    )
                canonical_name = (
                    target_root_access.context_name
                    + target_display_name[len(target_root_access.display_name) :]
                )
            else:
                if target_access.store.store_dir != target_root_access.store.store_dir:
                    raise ValueError(
                        "Recursive Merge Target descendants must share one Store."
                    )
                canonical_name = target_access.context_name
                existing_by_canonical_name[canonical_name] = target_contexts[
                    target_display_name
                ]
            canonical_target_names[source_name] = canonical_name

        sources = tuple(frame.context for frame in source_frames)
        target_by_source_uid = fresh_target_contexts(
            sources,
            target_names=canonical_target_names,
            existing_targets=existing_by_canonical_name,
        )
        source_by_uid = {source.uid: source for source in sources}
        target_frames: list[_RecursiveTargetFrame] = []
        context_results: list[MergeContextResult] = []
        all_additions = []
        all_unchanged = []
        all_conflicts = []
        any_cross_profile = False
        for frame in source_frames:
            source = frame.context
            target = target_by_source_uid[source.uid]
            target_display_name = display_target_name_by_source[source.name]
            target_access = target_access_by_display.get(target_display_name)
            authorization_target = target_access or target_root_access
            cross_profile = (
                frame.access.store.store_dir != target_root_access.store.store_dir
            )
            any_cross_profile = any_cross_profile or cross_profile
            expected_digest = (
                None
                if target_access is None
                else target._store_digest or context_record_digest(target)
            )
            projected = project_context_for_tree_merge(
                source,
                source_by_uid=source_by_uid,
                target_by_source_uid=target_by_source_uid,
                memory_only=cross_profile,
            )
            target_context_mutable, protected_target_uids = (
                _target_plan_protection(authorization_target, target)
            )
            context_plan = plan_context_merge(
                projected,
                target,
                source_name=frame.access.display_name,
                target_name=target_display_name,
                take_source_allowed=_take_source_allowed(authorization_target),
                target_context_mutable=target_context_mutable,
                protected_target_uids=protected_target_uids,
                lineage_target_uids=(
                    _lineage_target_uids(
                        frame.access,
                        target_access,
                        projected,
                        target,
                    )
                    if target_access is not None and not cross_profile
                    else {}
                ),
            )
            _require_planned_additions_mutable(
                target=target,
                context_plan=context_plan,
                target_context_mutable=target_context_mutable,
            )
            all_additions.extend(context_plan.additions)
            all_unchanged.extend(context_plan.unchanged)
            all_conflicts.extend(context_plan.conflicts)
            target_frames.append(
                _RecursiveTargetFrame(
                    access=target_access,
                    context=target,
                    source=projected,
                    context_plan=context_plan,
                    expected_digest=expected_digest,
                    records_memory_lineage=(
                        not cross_profile
                        and not frame.access.is_granted
                        and not authorization_target.is_granted
                    ),
                )
            )
            context_results.append(
                MergeContextResult(
                    source_name=frame.access.display_name,
                    source_uid=source.uid,
                    target_name=target_display_name,
                    target_uid=target.uid,
                    target_created=target_access is None,
                    additions=context_plan.additions,
                    unchanged=context_plan.unchanged,
                    conflicts=context_plan.conflicts,
                )
            )

        root_source = source_frames[0]
        root_target = target_frames[0]
        return FrozenMergePlan(
            request=request,
            source_name=source_root_access.display_name,
            source_uid=root_source.context.uid,
            source_digest=root_source.digest,
            target_name=target_root_access.display_name,
            target_uid=root_target.context.uid,
            target_digest=root_target.expected_digest
            or context_record_digest(root_target.context),
            additions=tuple(all_additions),
            contexts=tuple(context_results),
            cross_profile_memory_only=any_cross_profile,
            token=_RecursiveMergeToken(
                owner=self._owner,
                operation_uid=str(uuid.uuid4()),
                source_root_access=source_root_access,
                target_root_access=target_root_access,
                sources=source_frames,
                targets=tuple(target_frames),
                expected_source_names=tuple(
                    access.context_name for access in source_accesses
                ),
                expected_target_names=tuple(
                    access.context_name for access in target_accesses
                ),
            ),
            mutates_granted_authority=target_root_access.is_granted,
            unchanged=tuple(all_unchanged),
            conflicts=tuple(all_conflicts),
        )

    def apply(
        self,
        plan: FrozenMergePlan,
        resolutions: tuple[MergeResolution, ...],
    ) -> MergeResult:
        token = plan.token
        if isinstance(token, _RecursiveMergeToken):
            return self._apply_recursive(plan, token, resolutions)
        if not isinstance(token, _StoreMergeToken) or token.owner is not self._owner:
            raise ValueError("The frozen Merge plan belongs to another runtime.")
        source_access = token.source_access
        target_access = token.target_access
        target_store = target_access.store
        decisions = resolution_map(resolutions)
        candidate = materialize_context_merge(
            token.source,
            token.target,
            token.context_plan,
            resolutions=decisions,
        )
        contexts = [{"uid": candidate.uid, "name": candidate.name}]
        lineage_args = (
            {
                "memory_lineage": _merge_memory_lineage_record(
                    token.operation_uid,
                    token.source,
                    candidate,
                    token.context_plan,
                )
            }
            if not plan.cross_profile_memory_only
            and not source_access.is_granted
            and not target_access.is_granted
            else {}
        )
        checkpoint = AutoCheckpoint(
            command="merge",
            args={
                "source": source_access.display_name,
                "cross_profile_memory_only": plan.cross_profile_memory_only,
                "command_contexts": contexts,
                "merge_tree": {
                    "version": 2,
                    "operation_uid": token.operation_uid,
                    "source_root": plan.source_name,
                    "target_root": plan.target_name,
                    "target_created": False,
                },
                "merge_decisions": _merge_decision_checkpoint_record(
                    plan.conflicts,
                    resolutions,
                ),
                **lineage_args,
                **grant_checkpoint_args(target_access),
            },
            description=_merge_checkpoint_description(
                source_name=source_access.display_name,
                target_name=target_access.display_name,
                additions=plan.additions,
                unchanged_count=len(plan.unchanged),
                conflicts=plan.conflicts,
                resolutions=resolutions,
            ),
        )
        target_permissions = (
            ("CREATE", "UPDATE")
            if any(
                resolution.decision.value == "TAKE_SOURCE"
                for resolution in resolutions
            )
            else ("CREATE",)
        )
        with authorized_context_operation(
            (
                (source_access, ("READ",)),
                (target_access, target_permissions),
            )
        ):
            try:
                current_source = self._load_source(source_access)
            except FileNotFoundError as error:
                raise RuntimeError(
                    "The source Context no longer exists: "
                    f"'{source_access.context_name}'."
                ) from error
            if context_record_digest(current_source) != token.source_projection_digest:
                raise RuntimeError(
                    "The merge source changed before the target could be saved."
                )
            if plan.cross_profile_memory_only:
                saved = target_store.save(
                    candidate,
                    checkpoint,
                    expected_context_digest=plan.target_digest,
                )
            else:
                saved = target_store.save_context_with_sources(
                    candidate,
                    checkpoint,
                    expected_context_digest=plan.target_digest,
                    source_bindings=(
                        (
                            source_access.context_name,
                            plan.source_uid,
                            token.source_projection_digest,
                        ),
                    ),
                )
        if saved is None:
            raise RuntimeError("Merge saved no checkpoint.")
        return MergeResult(
            source_name=plan.source_name,
            source_uid=plan.source_uid,
            target_name=plan.target_name,
            target_uid=plan.target_uid,
            reach=plan.request.reach,
            additions=plan.additions,
            contexts=plan.contexts,
            checkpoint_uid=saved.uid,
            checkpoint_uids=(saved.uid,),
            cross_profile_memory_only=plan.cross_profile_memory_only,
            unchanged=plan.unchanged,
            conflicts=plan.conflicts,
            resolutions=resolutions,
        )

    def _apply_recursive(
        self,
        plan: FrozenMergePlan,
        token: _RecursiveMergeToken,
        resolutions: tuple[MergeResolution, ...],
    ) -> MergeResult:
        if token.owner is not self._owner:
            raise ValueError("The frozen Merge plan belongs to another runtime.")
        live_source_accesses = self._recursive_source_accesses(token.source_root_access)
        if tuple(
            (access.display_name, access.context_name, access.store.store_dir)
            for access in live_source_accesses
        ) != tuple(
            (
                frame.access.display_name,
                frame.access.context_name,
                frame.access.store.store_dir,
            )
            for frame in token.sources
        ):
            raise RuntimeError(
                "The Source Context subtree changed before the recursive Merge "
                "could be saved."
            )
        for frame, access in zip(token.sources, live_source_accesses, strict=True):
            current = self._load_source(access)
            if (
                current.uid != frame.context.uid
                or context_record_digest(current) != frame.digest
            ):
                raise RuntimeError(
                    "The merge source changed before the target could be saved."
                )
        live_target_accesses = self._recursive_target_accesses(token.target_root_access)
        if tuple(access.context_name for access in live_target_accesses) != (
            token.expected_target_names
        ):
            raise RuntimeError(
                "The Target Context subtree changed before the recursive Merge "
                "could be saved."
            )

        decisions = resolution_map(resolutions)
        candidates = tuple(
            materialize_context_merge(
                frame.source,
                frame.context,
                frame.context_plan,
                resolutions=decisions,
            )
            for frame in token.targets
        )
        contexts = [
            {"uid": frame.context.uid, "name": frame.context.name}
            for frame in token.targets
        ]
        writes: list[MergeTreeWrite] = []
        for result, frame, candidate in zip(
            plan.contexts,
            token.targets,
            candidates,
            strict=True,
        ):
            access = frame.access or token.target_root_access
            lineage_args = (
                {
                    "memory_lineage": _merge_memory_lineage_record(
                        token.operation_uid,
                        frame.source,
                        candidate,
                        frame.context_plan,
                    )
                }
                if frame.records_memory_lineage
                else {}
            )
            writes.append(
                MergeTreeWrite(
                    context=candidate,
                    expected_uid=frame.context.uid,
                    expected_digest=frame.expected_digest,
                    checkpoint=AutoCheckpoint(
                        command="merge",
                        args={
                            "source": result.source_name,
                            "cross_profile_memory_only": (
                                plan.cross_profile_memory_only
                            ),
                            "command_contexts": contexts,
                            "merge_tree": {
                                "version": 2,
                                "operation_uid": token.operation_uid,
                                "source_root": plan.source_name,
                                "target_root": plan.target_name,
                                "target_created": result.target_created,
                            },
                            "merge_decisions": _merge_decision_checkpoint_record(
                                result.conflicts,
                                resolutions,
                            ),
                            **lineage_args,
                            **grant_checkpoint_args(access),
                        },
                        description=_merge_checkpoint_description(
                            source_name=result.source_name,
                            target_name=result.target_name,
                            additions=result.additions,
                            unchanged_count=len(result.unchanged),
                            conflicts=result.conflicts,
                            resolutions=resolutions,
                            recursive=True,
                        ),
                    ),
                )
            )

        target_store = token.target_root_access.store
        same_store_sources = all(
            frame.access.store.store_dir == target_store.store_dir
            for frame in token.sources
        )
        source_bindings = (
            tuple(
                (frame.access.context_name, frame.context.uid, frame.digest)
                for frame in token.sources
            )
            if same_store_sources
            else ()
        )
        authority_pairs = [(frame.access, ("READ",)) for frame in token.sources]
        for frame in token.targets:
            if frame.access is None:
                continue
            take_source = any(
                decisions.get(conflict.uid) is not None
                and decisions[conflict.uid].value == "TAKE_SOURCE"
                for conflict in frame.context_plan.conflicts
            )
            authority_pairs.append(
                (frame.access, ("CREATE", "UPDATE") if take_source else ("CREATE",))
            )
        if any(frame.access is None for frame in token.targets):
            authority_pairs.append((token.target_root_access, ("CREATE",)))
        with authorized_context_operation(tuple(authority_pairs)):
            checkpoints = commit_merge_tree(
                target_store,
                tuple(writes),
                source_bindings=source_bindings,
                source_root=(
                    token.source_root_access.context_name
                    if same_store_sources
                    else None
                ),
                expected_source_names=(
                    token.expected_source_names if same_store_sources else ()
                ),
                target_root=token.target_root_access.context_name,
                expected_target_names=token.expected_target_names,
            )
        return MergeResult(
            source_name=plan.source_name,
            source_uid=plan.source_uid,
            target_name=plan.target_name,
            target_uid=plan.target_uid,
            reach=plan.request.reach,
            additions=plan.additions,
            contexts=plan.contexts,
            checkpoint_uid=checkpoints[0].uid,
            checkpoint_uids=tuple(checkpoint.uid for checkpoint in checkpoints),
            cross_profile_memory_only=plan.cross_profile_memory_only,
            unchanged=plan.unchanged,
            conflicts=plan.conflicts,
            resolutions=resolutions,
        )


def merge_summary(additions: tuple[MergeAddition, ...]) -> str:
    """Return the stable direct CLI/checkpoint count phrase."""

    labels = (
        (MergeItemKind.MEMORY, "memory", "memories"),
        (MergeItemKind.MEMORY_REF, "memory ref", "memory refs"),
        (MergeItemKind.QUERY_VIEW, "query view", "query views"),
        (MergeItemKind.CONTEXT, "embedded context", "embedded contexts"),
    )
    parts: list[str] = []
    for kind, singular, plural in labels:
        count = sum(addition.kind is kind for addition in additions)
        if count:
            parts.append(f"{count} {singular if count == 1 else plural}")
    return ", ".join(parts) if parts else "0 items"


def execute_merge(
    request: MergeRequest,
    *,
    store: MemoryStore,
    resolutions: tuple[MergeResolution, ...] = (),
    bulk: MergeDecision | None = None,
) -> MergeResult:
    """Execute Merge against a real Store with no terminal output."""

    if bulk is not None and not isinstance(bulk, MergeDecision):
        raise TypeError("Merge bulk decision must be a MergeDecision.")
    return run_merge(
        request,
        port=MemoryStoreMergePort.capture(store),
        resolutions=resolutions,
        bulk=bulk,
    )
