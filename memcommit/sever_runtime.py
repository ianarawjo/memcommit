"""Production Store, authority, cache, provider, and Apply adapters for Sever."""

from __future__ import annotations

from dataclasses import dataclass
import uuid

# Transitional dependency: Grant access mechanics still live under commands.
# Keeping them in this Store adapter prevents the terminal-independent
# application boundary from depending on the CLI package during the rollout.
from memcommit.commands.granted_context import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
)
from memcommit.command_attempts import annotate_sever_attempt
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef, QueryContextRef
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.derived_policy import (
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.query_provider import QueryProviderError, QueryProviderTimeoutError
from memcommit.sever import (
    SeverApplication,
    SeverContextBinding,
    SeverMemory,
    SeverSession,
    sever_frame_digest,
    sever_record_digest,
)
from memcommit.sever_application import (
    FrozenSeverInputs,
    SeverAnalysisRequest,
    SeverAnalysisResult,
    SeverApplicationError,
    SeverApplyRequest,
    SeverApplyResult,
    SeverPreparedAnalysis,
    SeverProviderFactory,
    SeverProgressObserver,
    run_sever_analysis,
    run_sever_apply,
)
from memcommit.sever_provider import SeverProviderError
from memcommit.store import MemoryStore, context_record_digest, validate_context_name
from memcommit.study_prewarm.sever import find_installed_projectable_sever_prewarm


SeverProgressCallback = SeverProgressObserver


def capture_sever_binding(
    access: ContextAccess,
    *,
    include_descendants: bool,
) -> SeverContextBinding:
    """Freeze one authorized ordinary-Memory frame for analysis and later CAS."""

    read_store: MemoryStore | GrantedReadStore = (
        GrantedReadStore(access) if access.is_granted else access.store
    )
    root_name = access.display_name if access.is_granted else access.context_name
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
        root_name=access.display_name,
        frame_digest=sever_frame_digest(
            root_uid=root.uid,
            root_name=access.display_name,
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
        display_name=name,
        attachment_name=None,
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
        source_access = resolve_context_access(
            self._store,
            request.source_locator,
            current_name=self._current_name,
            required_permission="READ",
        )
        criteria_access = resolve_context_access(
            self._store,
            request.criteria_locator,
            current_name=self._current_name,
            required_permission="READ",
        )
        if (
            source_access.display_name == criteria_access.display_name
            and source_access.store.store_dir == criteria_access.store.store_dir
        ):
            raise SeverApplicationError(
                "Source and Criteria Contexts must be distinct."
            )
        validate_context_name(request.output_name)
        if self._store.context_exists(request.output_name):
            raise SeverApplicationError(
                f"Output Context '{request.output_name}' already exists."
            )
        output_access = _local_output_access(self._store, request.output_name)
        authorize_combination((source_access, criteria_access))
        authorize_derived_transfer(source_access, output_access)
        authorize_derived_transfer(criteria_access, output_access)
        authorize_analysis_save(
            (source_access, criteria_access),
            retention="RETAINED",
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
        annotate_sever_attempt(
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
            output_name=request.output_name,
            excluded_query_context_count=len(
                set(frozen.source.excluded_query_context_names)
                | set(frozen.criteria.excluded_query_context_names)
            ),
        )
        return frozen


def _provider_with_attempt_evidence(factory: SeverProviderFactory) -> object:
    provider = factory()
    identity = getattr(provider, "identity", None)
    provider_name = getattr(identity, "provider", None)
    provider_timeout = getattr(provider, "timeout", None)
    details: dict[str, object] = {}
    if isinstance(provider_name, str) and provider_name:
        details["provider"] = provider_name
    if (
        isinstance(provider_timeout, (int, float))
        and not isinstance(provider_timeout, bool)
        and provider_timeout > 0
    ):
        details["provider_timeout_seconds"] = provider_timeout
    if details:
        annotate_sever_attempt(**details)
    return provider


def execute_sever_analysis(
    request: SeverAnalysisRequest,
    *,
    store: MemoryStore,
    provider_factory: SeverProviderFactory,
    progress_callback: SeverProgressCallback | None = None,
) -> SeverAnalysisResult:
    """Execute Sever analysis with no CLI, TUI, or terminal output."""

    input_port = MemoryStoreSeverInputPort.capture(store)
    try:
        return run_sever_analysis(
            request,
            input_port=input_port,
            provider_factory=lambda: _provider_with_attempt_evidence(
                provider_factory
            ),
            prepared_lookup=lambda inputs, output_name: _prepared_analysis(
                store,
                inputs,
                output_name,
            ),
            progress_observer=progress_callback,
        )
    except QueryProviderError as error:
        annotate_sever_attempt(
            failure_kind=(
                "TIMEOUT"
                if isinstance(error, QueryProviderTimeoutError)
                else "PROVIDER"
            )
        )
        frozen = input_port.last_frozen
        frame = (
            f" Frozen frame: {len(frozen.source.memories)} Source Memories x "
            f"{len(frozen.criteria.memories)} Criteria Memories."
            if frozen is not None
            else ""
        )
        raise SeverApplicationError(f"{error}{frame}") from error
    except SeverProviderError:
        annotate_sever_attempt(failure_kind="VALIDATION")
        raise


def _prepared_analysis(
    store: MemoryStore,
    inputs: FrozenSeverInputs,
    output_name: str,
) -> SeverPreparedAnalysis | None:
    match = find_installed_projectable_sever_prewarm(
        store=store,
        source=inputs.source,
        criteria=inputs.criteria,
        output_name=output_name,
    )
    if match is None:
        return None
    if match.origin == "EXACT_PREWARM":
        return SeverPreparedAnalysis(
            session=match.session,
            origin="EXACT_PREWARM",
        )
    if match.origin == "EQUIVALENT_SCOPE_PREWARM":
        return SeverPreparedAnalysis(
            session=match.session,
            origin="EQUIVALENT_SCOPE_PREWARM",
        )
    if match.origin == "PROJECTED_PREWARM":
        return SeverPreparedAnalysis(
            session=match.session,
            origin="PROJECTED_PREWARM",
        )
    raise SeverApplicationError(
        "The prepared Sever analysis has an unsupported origin."
    )


def _result_uid(session_uid: str, source_uid: str, content: str) -> str:
    return str(
        uuid.uuid5(uuid.UUID(session_uid), f"result\x1f{source_uid}\x1f{content}")
    )


@dataclass
class MemoryStoreSeverOutputPort:
    """Publish a reviewed local Result and its checkpoint under Store CAS."""

    store: MemoryStore

    def materialize(self, session: SeverSession) -> SeverSession:
        output = Context(uid=str(uuid.uuid4()), name=session.output_name)
        result_uids: list[str] = []
        sources: list[dict[str, str]] = []
        for candidate, source, content in session.results():
            uid = _result_uid(session.uid, source.uid, content)
            output.add(Memory(uid=uid, content=content))
            result_uids.append(uid)
            sources.append(
                {
                    "candidate_uid": candidate.uid,
                    "source_context": source.context_name,
                    "source_memory_uid": source.uid,
                    "selection": candidate.selection,
                }
            )

        local_bindings: list[tuple[str, str, str]] = []
        for binding in (session.source, session.criteria):
            if binding.granted is None:
                local_bindings.extend(binding.contexts)
        deduplicated = tuple(dict.fromkeys(local_bindings))
        auto_checkpoint = AutoCheckpoint(
            command="sever",
            args={
                "context_creation": {
                    "version": 1,
                    "context_uid": output.uid,
                    "context_name": output.name,
                },
                "sever": {
                    "session_uid": session.uid,
                    "session_digest": sever_record_digest(session),
                    "source": session.source.root_name,
                    "source_scope": (
                        "INCLUDE_DESCENDANTS"
                        if session.source.include_descendants
                        else "THIS_CONTEXT_ONLY"
                    ),
                    "criteria": session.criteria.root_name,
                    "criteria_scope": (
                        "INCLUDE_DESCENDANTS"
                        if session.criteria.include_descendants
                        else "THIS_CONTEXT_ONLY"
                    ),
                    "output": session.output_name,
                    "results": sources,
                },
            },
            description=(
                f"Created local Sever result '{session.output_name}' from "
                f"'{session.source.root_name}' under '{session.criteria.root_name}'; "
                "source unchanged"
            ),
        )
        if deduplicated:
            checkpoint = self.store.create_context_with_sources(
                output,
                auto_checkpoint,
                source_bindings=deduplicated,
            )
        else:
            # Granted frames are retained snapshots and have no local Context
            # path to lock while the require-new local output is published.
            checkpoint = self.store.create_context(output, auto_checkpoint)
        if checkpoint is None:
            raise SeverApplicationError(
                "Sever output creation produced no checkpoint."
            )
        return session.with_application(
            SeverApplication(
                output_context_uid=output.uid,
                checkpoint_uid=checkpoint.uid,
                result_memory_uids=tuple(result_uids),
            )
        )


def execute_sever_apply(
    request: SeverApplyRequest,
    *,
    store: MemoryStore,
) -> SeverApplyResult:
    """Apply one exact review through the production require-new Store port."""

    return run_sever_apply(
        request,
        output_port=MemoryStoreSeverOutputPort(store),
    )
