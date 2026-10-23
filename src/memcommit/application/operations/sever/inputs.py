"""Resolve and freeze Sever inputs for analysis and Apply revalidation."""

from __future__ import annotations

from memcommit.application.context_access.access import ContextAccess
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.application.operations.sever.application import (
    FrozenSeverInputs,
    SeverAnalysisRequest,
    SeverApplicationError,
)
from memcommit.application.operations.sever.model import (
    SeverContextBinding,
    SeverMemory,
    sever_frame_digest,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.core.context_name_validation import validate_context_name
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.persistence.command_ledger.attempts import annotate_sever_attempt
from memcommit.persistence.store import (
    MemoryStore,
)


def capture_sever_binding(
    access: ContextAccess,
    *,
    include_descendants: bool,
) -> SeverContextBinding:
    """Freeze one authorized ordinary-Memory frame for analysis and later CAS."""

    read_store: MemoryStore = access.store
    root_name = access.context_name
    load_direct = read_store.load_direct
    load_recursive = read_store.load
    root = load_recursive(root_name) if include_descendants else load_direct(root_name)
    roots = [root]
    if include_descendants:
        seen_root_uids = {root.uid}
        for name in expand_lexical_context_names(
            (root_name,),
            read_store.list_context_names(),
            include_descendants=include_descendants,
        )[1:]:
            descendant = load_recursive(name)
            if descendant.uid in seen_root_uids:
                continue
            seen_root_uids.add(descendant.uid)
            roots.append(descendant)

    contexts: list[tuple[str, str]] = []
    memories: list[SeverMemory] = []
    seen_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in seen_contexts:
            return
        seen_contexts.add(context.uid)
        contexts.append((context.name, context.uid))
        for item in context.iter_memories():
            if isinstance(item, Memory):
                memories.append(
                    SeverMemory(
                        uid=item.uid,
                        context_name=context.name,
                        content=item.content,
                    )
                )

    for frame_root in roots:
        visit(frame_root)
    context_tuple = tuple(contexts)
    memory_tuple = tuple(memories)
    return SeverContextBinding(
        root_uid=root.uid,
        root_name=access.access_name,
        frame_digest=sever_frame_digest(
            root_uid=root.uid,
            root_name=access.access_name,
            contexts=context_tuple,
            memories=memory_tuple,
            include_descendants=include_descendants,
        ),
        contexts=context_tuple,
        memories=memory_tuple,
        include_descendants=include_descendants,
    )


def _local_output_access(store: MemoryStore, name: str) -> ContextAccess:
    return ContextAccess(
        store=store,
        context_name=name,
        access_name=name,
    )


class MemoryStoreSeverInputPort:
    """Resolve and freeze one Sever request against one current-name snapshot."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        self._current_name = current_name
        self.last_frozen: FrozenSeverInputs | None = None

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreSeverInputPort":
        return cls(store, current_name=store.current_context_name())

    def freeze(self, request: SeverAnalysisRequest) -> FrozenSeverInputs:
        candidates = freeze_profile_context_access_candidates(
            self._store,
            current_name=self._current_name,
        )
        source_access = resolve_existing_context_access(
            self._store,
            request.source_locator,
            current_name=self._current_name,
            candidates=candidates,
        ).value
        criteria_access = resolve_existing_context_access(
            self._store,
            request.criteria_locator,
            current_name=self._current_name,
            candidates=candidates,
        ).value
        if (
            source_access.access_name == criteria_access.access_name
            and source_access.store.store_dir == criteria_access.store.store_dir
        ):
            raise SeverApplicationError(
                "Source and Criteria Contexts must be distinct."
            )
        validate_context_name(request.output_name)
        same_source_name = request.output_name == source_access.access_name
        if same_source_name and (
            False or source_access.store.store_dir != self._store.store_dir
        ):
            raise SeverApplicationError(
                "In-place Sever requires an ordinary local Source."
            )
        self_save = (
            same_source_name and source_access.store.store_dir == self._store.store_dir
        )
        if self._store.context_exists(request.output_name) and not self_save:
            raise SeverApplicationError(
                f"Output Context '{request.output_name}' already exists."
            )
        frozen = FrozenSeverInputs(
            source=capture_sever_binding(
                source_access,
                include_descendants=request.source_include_descendants,
            ),
            criteria=capture_sever_binding(
                criteria_access,
                include_descendants=request.criteria_include_descendants,
            ),
        )
        self.last_frozen = frozen
        attempt_details: dict[str, object] = dict(
            source_name=frozen.source.root_name,
            source_scope=(
                "INCLUDE_DESCENDANTS"
                if frozen.source.include_descendants
                else "THIS_CONTEXT_ONLY"
            ),
            source_memory_count=len(frozen.source.memories),
            criteria_name=frozen.criteria.root_name,
            criteria_scope=(
                "INCLUDE_DESCENDANTS"
                if frozen.criteria.include_descendants
                else "THIS_CONTEXT_ONLY"
            ),
            criteria_memory_count=len(frozen.criteria.memories),
        )
        # New Sever invocations have no output endpoint to report. Keep the
        # legacy field only for resumable OTHER_SAVE sessions and their logs.
        if not self_save:
            attempt_details["output_name"] = request.output_name
        annotate_sever_attempt(**attempt_details)
        return frozen
