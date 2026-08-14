"""MemoryStore and Grant infrastructure adapter for structural Merge."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import memcommit.ops as ops
from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    authorized_context_operation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Information,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.derived_policy import authorize_derived_transfer
from memcommit.merge_application import (
    FrozenMergePlan,
    MergeAddition,
    MergeContextResult,
    MergeItemKind,
    MergePort,
    MergeReach,
    MergeRequest,
    MergeResult,
    run_merge,
)
from memcommit.merge_tree import (
    align_context_names,
    fresh_target_contexts,
    project_context_for_tree_merge,
)
from memcommit.merge_tree_persistence import MergeTreeWrite, commit_merge_tree
from memcommit.store import MemoryStore, context_record_digest


def _memory_only_source(source: Context) -> Context:
    """Copy portable Memory values without carrying cross-Profile pointers."""

    result = Context(uid=source.uid, name=source.name)
    for item in source.iter_items():
        if isinstance(item, Memory):
            result.add(Memory(uid=item.uid, content=item.content))
    return result


def _addition(item: Information) -> MergeAddition:
    if isinstance(item, Memory):
        kind = MergeItemKind.MEMORY
    elif isinstance(item, MemoryRef):
        kind = MergeItemKind.MEMORY_REF
    elif isinstance(item, QueryContextRef):
        kind = MergeItemKind.QUERY_VIEW
    elif isinstance(item, Context):
        kind = MergeItemKind.CONTEXT
    else:  # pragma: no cover - Information is a closed type alias.
        raise TypeError("Merge produced an unsupported direct item.")
    return MergeAddition(uid=item.uid, kind=kind)


@dataclass(frozen=True)
class _StoreMergeToken:
    """Bind a frozen direct plan to its exact authority and candidate state."""

    owner: object
    source_access: ContextAccess
    target_access: ContextAccess
    candidate: Context
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
    expected_digest: str | None

    @property
    def created(self) -> bool:
        return self.expected_digest is None


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
    """Plan and commit direct Merge against one current-name snapshot."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreMergePort":
        return cls(store, current_name=store.current_context_name())

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
        source_access = resolve_context_access(
            self._store,
            request.source_locator,
            current_name=self._current_name,
            required_permission="READ",
        )
        target_access = resolve_context_access(
            self._store,
            request.target_locator,
            current_name=self._current_name,
            required_permission="CREATE",
        )
        source = self._load_source(source_access)
        target = target_access.store.load_for_update(target_access.context_name)
        authorize_derived_transfer(source_access, target_access)
        if (
            target.uid == source.uid
            and source_access.store.store_dir == target_access.store.store_dir
        ):
            raise ValueError("cannot merge a context into itself.")

        cross_profile = source_access.store.store_dir != target_access.store.store_dir
        merge_source = _memory_only_source(source) if cross_profile else source
        source_projection_digest = context_record_digest(source)
        target_digest = target._store_digest or context_record_digest(target)
        added = ops.merge(merge_source, target)
        additions = tuple(_addition(item) for item in added)
        context_result = MergeContextResult(
            source_name=source_access.display_name,
            source_uid=source.uid,
            target_name=target_access.display_name,
            target_uid=target.uid,
            target_created=False,
            additions=additions,
        )
        return FrozenMergePlan(
            request=request,
            source_name=source_access.display_name,
            source_uid=source.uid,
            source_digest=source_projection_digest,
            target_name=target_access.display_name,
            target_uid=target.uid,
            target_digest=target_digest,
            additions=additions,
            contexts=(context_result,),
            cross_profile_memory_only=cross_profile,
            token=_StoreMergeToken(
                owner=self._owner,
                source_access=source_access,
                target_access=target_access,
                candidate=target,
                source_projection_digest=source_projection_digest,
            ),
        )

    def _freeze_recursive(self, request: MergeRequest) -> FrozenMergePlan:
        source_root_access = resolve_context_access(
            self._store,
            request.source_locator,
            current_name=self._current_name,
            required_permission="READ",
        )
        target_root_access = resolve_context_access(
            self._store,
            request.target_locator,
            current_name=self._current_name,
            required_permission="CREATE",
        )
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
        all_additions: list[MergeAddition] = []
        any_cross_profile = False
        for frame in source_frames:
            source = frame.context
            target = target_by_source_uid[source.uid]
            target_display_name = display_target_name_by_source[source.name]
            target_access = target_access_by_display.get(target_display_name)
            authorization_target = target_access or target_root_access
            authorize_derived_transfer(frame.access, authorization_target)
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
            additions = tuple(_addition(item) for item in ops.merge(projected, target))
            all_additions.extend(additions)
            target_frames.append(
                _RecursiveTargetFrame(
                    access=target_access,
                    context=target,
                    expected_digest=expected_digest,
                )
            )
            context_results.append(
                MergeContextResult(
                    source_name=frame.access.display_name,
                    source_uid=source.uid,
                    target_name=target_display_name,
                    target_uid=target.uid,
                    target_created=target_access is None,
                    additions=additions,
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
        )

    def apply(self, plan: FrozenMergePlan) -> MergeResult:
        token = plan.token
        if isinstance(token, _RecursiveMergeToken):
            return self._apply_recursive(plan, token)
        if not isinstance(token, _StoreMergeToken) or token.owner is not self._owner:
            raise ValueError("The frozen Merge plan belongs to another runtime.")
        source_access = token.source_access
        target_access = token.target_access
        target_store = target_access.store
        candidate = token.candidate
        summary = merge_summary(plan.additions)
        checkpoint = AutoCheckpoint(
            command="merge",
            args={
                "source": source_access.display_name,
                "cross_profile_memory_only": plan.cross_profile_memory_only,
                **grant_checkpoint_args(target_access),
            },
            description=(
                f"Merged '{source_access.display_name}' into "
                f"'{target_access.display_name}': added {summary}"
            ),
        )
        with authorized_context_operation(
            (
                (source_access, ("READ",)),
                (target_access, ("CREATE",)),
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
        )

    def _apply_recursive(
        self,
        plan: FrozenMergePlan,
        token: _RecursiveMergeToken,
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

        contexts = [
            {"uid": frame.context.uid, "name": frame.context.name}
            for frame in token.targets
        ]
        writes: list[MergeTreeWrite] = []
        for result, frame in zip(plan.contexts, token.targets, strict=True):
            access = frame.access or token.target_root_access
            summary = merge_summary(result.additions)
            writes.append(
                MergeTreeWrite(
                    context=frame.context,
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
                                "version": 1,
                                "operation_uid": token.operation_uid,
                                "source_root": plan.source_name,
                                "target_root": plan.target_name,
                            },
                            **grant_checkpoint_args(access),
                        },
                        description=(
                            f"Recursively merged '{result.source_name}' into "
                            f"'{result.target_name}': added {summary}"
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
        authority_pairs = [(frame.access, ("READ",)) for frame in token.sources] + [
            (frame.access, ("CREATE",))
            for frame in token.targets
            if frame.access is not None
        ]
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
    return ", ".join(parts) if parts else "nothing new"


def execute_merge(request: MergeRequest, *, store: MemoryStore) -> MergeResult:
    """Execute Merge against a real Store with no terminal output."""

    return run_merge(request, port=MemoryStoreMergePort.capture(store))
