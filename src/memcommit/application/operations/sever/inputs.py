"""Resolve and freeze Sever inputs for analysis and Apply revalidation."""

from __future__ import annotations

from memcommit.application.capabilities.semantic.disclosure import (
    SemanticDisclosureError,
    require_semantic_disclosure_authority,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.application.operations.profile.config import ProfileRegistry
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
from memcommit.core.context import (
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.persistence.command_ledger.attempts import annotate_sever_attempt
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)


def capture_sever_binding(
    access: ContextAccess,
    *,
    include_descendants: bool,
    registry: ProfileRegistry | None = None,
) -> SeverContextBinding:
    """Freeze one authorized ordinary-Memory frame for analysis and later CAS."""

    read_store: MemoryStore | GrantedReadStore = (
        GrantedReadStore(access, registry=registry)
        if access.is_granted
        else access.store
    )
    root_name = access.access_name if access.is_granted else access.context_name
    load_direct = read_store.load_direct
    load_recursive = read_store.load
    scope = ContextScope.create(
        (root_name,),
        include_descendants=include_descendants,
    )
    root = load_recursive(root_name) if include_descendants else load_direct(root_name)
    roots = [root]
    if include_descendants:
        seen_root_uids = {root.uid}
        # Namespace descendants and embedded children are independent routes
        # into the same semantic frame, so UID de-duplication prevents double
        # provider exposure when both routes reach one Context.
        for name in expand_lexical_context_names(
            scope,
            read_store.list_context_names(),
        )[1:]:
            descendant = load_recursive(name)
            if descendant.uid in seen_root_uids:
                continue
            seen_root_uids.add(descendant.uid)
            roots.append(descendant)

    try:
        require_semantic_disclosure_authority(
            roots,
            operation="Sever",
            follow_contexts=include_descendants,
        )
    except SemanticDisclosureError as error:
        raise SeverApplicationError(str(error)) from error

    contexts: list[tuple[str, str, str]] = []
    memories: list[SeverMemory] = []
    excluded_query_context_names: list[str] = []
    seen_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in seen_contexts:
            return
        seen_contexts.add(context.uid)
        contexts.append((context.name, context.uid, context_record_digest(context)))
        for item in context.iter_items():
            if isinstance(item, Memory):
                memories.append(
                    SeverMemory(
                        uid=item.uid,
                        context_name=context.name,
                        content=item.content,
                    )
                )
            elif isinstance(item, Context):
                if include_descendants:
                    visit(item)
            elif isinstance(item, QueryContextRef):
                # QUERY authority does not disclose hidden content to Sever.
                if item.name not in excluded_query_context_names:
                    excluded_query_context_names.append(item.name)
            elif isinstance(item, MemoryRef):
                raise SeverApplicationError(
                    f"Sever does not copy live Memory references from '{context.name}'."
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
        granted=(
            freeze_granted_context_binding(access).to_dict()
            if access.is_granted
            else None
        ),
        include_descendants=include_descendants,
        excluded_query_context_names=tuple(excluded_query_context_names),
    )


def _local_output_access(store: MemoryStore, name: str) -> ContextAccess:
    return ContextAccess(
        store=store,
        context_name=name,
        access_name=name,
        permission="CREATE",
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
            required_permission="READ",
            candidates=candidates,
        ).value
        criteria_access = resolve_existing_context_access(
            self._store,
            request.criteria_locator,
            current_name=self._current_name,
            required_permission="READ",
            candidates=candidates,
        ).value
        if (
            source_access.access_name == criteria_access.access_name
            and source_access.store.store_dir == criteria_access.store.store_dir
        ):
            raise SeverApplicationError(
                "Source and Criteria Contexts must be distinct."
            )
        validate_portable_context_name(request.output_name)
        same_source_name = request.output_name == source_access.access_name
        if same_source_name and (
            source_access.is_granted
            or source_access.store.store_dir != self._store.store_dir
        ):
            raise SeverApplicationError(
                "In-place Sever requires an ordinary local Source."
            )
        self_save = (
            same_source_name
            and not source_access.is_granted
            and source_access.store.store_dir == self._store.store_dir
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
            excluded_query_context_count=len(
                set(frozen.source.excluded_query_context_names)
                | set(frozen.criteria.excluded_query_context_names)
            ),
        )
        # New Sever invocations have no output endpoint to report. Keep the
        # legacy field only for resumable OTHER_SAVE sessions and their logs.
        if not self_save:
            attempt_details["output_name"] = request.output_name
        annotate_sever_attempt(**attempt_details)
        return frozen
