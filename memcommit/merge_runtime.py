"""MemoryStore and Grant infrastructure adapter for structural Merge."""

from __future__ import annotations

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
from memcommit.derived_policy import authorize_derived_transfer
from memcommit.merge_application import (
    FrozenMergePlan,
    MergeAddition,
    MergeItemKind,
    MergePort,
    MergeRequest,
    MergeResult,
    run_merge,
)
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

    def freeze(self, request: MergeRequest) -> FrozenMergePlan:
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
        return FrozenMergePlan(
            request=request,
            source_name=source_access.display_name,
            source_uid=source.uid,
            source_digest=source_projection_digest,
            target_name=target_access.display_name,
            target_uid=target.uid,
            target_digest=target_digest,
            additions=additions,
            cross_profile_memory_only=cross_profile,
            token=_StoreMergeToken(
                owner=self._owner,
                source_access=source_access,
                target_access=target_access,
                candidate=target,
                source_projection_digest=source_projection_digest,
            ),
        )

    def apply(self, plan: FrozenMergePlan) -> MergeResult:
        token = plan.token
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
            checkpoint_uid=saved.uid,
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
