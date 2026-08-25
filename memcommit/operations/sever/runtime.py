"""Production Store, authority, cache, provider, and Apply adapters for Sever."""

from __future__ import annotations

from dataclasses import dataclass, replace
import uuid

# Transitional dependency: Grant access mechanics still live under commands.
# Keeping them in this Store adapter prevents the terminal-independent
# application boundary from depending on the CLI package during the rollout.
from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.command_attempts import annotate_sever_attempt
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef, QueryContextRef
from memcommit.context_naming import validate_portable_context_name
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.derived_policy import (
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.query_provider import QueryProviderError, QueryProviderTimeoutError
from memcommit.semantic_disclosure import (
    SemanticDisclosureError,
    require_semantic_disclosure_authority,
)
from memcommit.profile_config import ProfileRegistry
from memcommit.profiles import ProfileError, authority_grant_snapshot_lock
from memcommit.sever import (
    SeverApplication,
    SeverContextBinding,
    SeverMemory,
    SeverSession,
    sever_frame_digest,
    sever_record_digest,
)
from memcommit.operations.sever.application import (
    FrozenSeverInputs,
    SeverAnalysisRequest,
    SeverAnalysisResult,
    SeverApplicationError,
    SeverApplyRequest,
    SeverApplyResult,
    SeverDecisionRequest,
    SeverDestinationRequest,
    SeverPersistedApplyRequest,
    SeverPersistedApplyResult,
    SeverPreparedAnalysis,
    SeverProviderFactory,
    SeverProgressObserver,
    SeverSessionSnapshot,
    SeverStoredAnalysisResult,
    run_sever_analysis,
    run_sever_apply,
    run_sever_session_apply,
    run_sever_session_decision,
    run_sever_session_destination_change,
    run_sever_session_open,
    run_sever_session_start,
)
from memcommit.sever_provider import SeverProviderError
from memcommit.sever_store import SeverSessionStore
from memcommit.store import MemoryStore, _write_json_atomic, context_record_digest
from memcommit.study_prewarm.sever import find_installed_projectable_sever_prewarm
from memcommit.update import GrantedUpdateTarget


SeverProgressCallback = SeverProgressObserver


@dataclass
class MemoryStoreSeverSessionRepository:
    """Private Store-backed session persistence with opaque digest CAS tokens."""

    store: MemoryStore

    @property
    def sessions(self) -> SeverSessionStore:
        return SeverSessionStore(self.store)

    @staticmethod
    def _snapshot(session: SeverSession) -> SeverSessionSnapshot:
        return SeverSessionSnapshot(
            session=session,
            version_token=sever_record_digest(session),
        )

    def create(self, session: SeverSession) -> SeverSessionSnapshot:
        self.sessions.save(session, expected_digest=None)
        return self._snapshot(session)

    def load(self, uid: str) -> SeverSessionSnapshot:
        return self._snapshot(self.sessions.load(uid))

    def replace(
        self,
        session: SeverSession,
        *,
        expected_version: str,
    ) -> SeverSessionSnapshot:
        self.sessions.save(session, expected_digest=expected_version)
        return self._snapshot(session)


@dataclass
class MemoryStoreSeverDestinationPort:
    """Validate one local self- or other-save destination against the live Store."""

    store: MemoryStore
    source_name: str
    self_save_allowed: bool

    def validate(self, output_name: str, *, current_output_name: str) -> None:
        validate_portable_context_name(output_name)
        if output_name == self.source_name:
            if not self.self_save_allowed:
                raise SeverApplicationError(
                    "Self-save requires an ordinary local Source root with "
                    "Source descendants excluded."
                )
            return
        if output_name != current_output_name and self.store.context_exists(output_name):
            raise SeverApplicationError(
                f"Output Context '{output_name}' already exists."
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
        validate_portable_context_name(request.output_name)
        same_source_name = request.output_name == source_access.display_name
        if same_source_name and (
            source_access.is_granted
            or source_access.store.store_dir != self._store.store_dir
        ):
            raise SeverApplicationError(
                "Self-save requires an ordinary local Source. Save to a fresh "
                "local Result when Source is granted."
            )
        self_save = (
            same_source_name
            and not source_access.is_granted
            and source_access.store.store_dir == self._store.store_dir
        )
        if self_save and request.source_include_descendants:
            # A root-only self-save can preserve one Context's complete direct
            # structure and Memory identities. Recursive self-save needs an
            # owner-aware multi-Context receipt; rejecting it prevents a
            # flattened Result from only partially mutating the Source tree.
            raise SeverApplicationError(
                "Self-save requires Source descendants to be excluded. "
                "Use --source-root-only or save the recursive Result elsewhere."
            )
        if self._store.context_exists(request.output_name) and not self_save:
            raise SeverApplicationError(
                f"Output Context '{request.output_name}' already exists."
            )
        output_access = (
            source_access
            if self_save
            else _local_output_access(self._store, request.output_name)
        )
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
            f" Prepared input: {len(frozen.source.memories)} Source Memories x "
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
    """Publish a reviewed self- or other-save Result under Store CAS."""

    store: MemoryStore

    @staticmethod
    def _result_context(
        session: SeverSession,
        *,
        output_uid: str,
    ) -> tuple[Context, tuple[str, ...], list[dict[str, str]]]:
        output = Context(uid=output_uid, name=session.output_name)
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
        return output, tuple(result_uids), sources

    @staticmethod
    def _self_save_source_receipt(session: SeverSession) -> tuple[str, str, str]:
        """Return the one exact direct Source owner allowed for self-save."""

        if (
            session.save_mode != "SELF_SAVE"
            or session.source.granted is not None
            or session.source.include_descendants
            or len(session.source.contexts) != 1
        ):
            raise SeverApplicationError(
                "Self-save requires one ordinary local Source root with "
                "Source descendants excluded."
            )
        receipt = session.source.contexts[0]
        if receipt[0] != session.source.root_name:
            raise SeverApplicationError(
                "The self-save Source receipt does not identify its root Context."
            )
        return receipt

    @classmethod
    def _self_save_context(
        cls,
        session: SeverSession,
        original: Context,
    ) -> tuple[Context, tuple[str, ...], list[dict[str, str]]]:
        """Project reviewed treatments onto the same direct Context identity."""

        source_name, source_uid, source_digest = cls._self_save_source_receipt(session)
        if (
            original.name != source_name
            or original.uid != source_uid
            or context_record_digest(original) != source_digest
        ):
            raise SeverApplicationError(
                "The self-save Source changed after review. Re-run Sever."
            )
        output = Context.from_dict(original.to_dict())
        retained = {
            source.uid: (candidate, content)
            for candidate, source, content in session.results()
        }
        result_uids: list[str] = []
        sources: list[dict[str, str]] = []
        for candidate in session.candidates:
            source = session.source_memory(candidate.source_memory_uid)
            current = output.memories.get(source.uid)
            if (
                source.context_name != source_name
                or not isinstance(current, Memory)
                or current.content != source.content
            ):
                raise SeverApplicationError(
                    "The self-save Source no longer contains its reviewed Memories."
                )
            retained_result = retained.get(source.uid)
            if retained_result is None:
                output.remove(source.uid)
            else:
                _retained_candidate, content = retained_result
                output.replace(Memory(uid=source.uid, content=content))
                result_uids.append(source.uid)
            sources.append(
                {
                    "candidate_uid": candidate.uid,
                    "source_context": source.context_name,
                    "source_memory_uid": source.uid,
                    "selection": candidate.selection,
                }
            )
        return output, tuple(result_uids), sources

    @staticmethod
    def _checkpoint_args(
        session: SeverSession,
        output: Context,
        sources: list[dict[str, str]],
    ) -> dict[str, object]:
        args: dict[str, object] = {
            "sever": {
                "save_mode": session.save_mode,
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
        }
        if session.save_mode == "OTHER_SAVE":
            args["context_creation"] = {
                "version": 1,
                "context_uid": output.uid,
                "context_name": output.name,
            }
        return args

    def recover_materialization(self, session: SeverSession) -> SeverSession | None:
        """Adopt only an untouched Result produced by this exact review.

        A process can stop after the atomic Context/checkpoint creation but
        before the private session CAS. The exact checkpoint is sufficient to
        restore that missing receipt; an unrelated occupant remains an ordinary
        require-new name collision.
        """

        if not self.store.context_exists(session.output_name):
            return None
        if session.save_mode == "SELF_SAVE":
            return self._recover_self_save(session)
        current = self.store.load_direct(session.output_name)
        expected, result_uids, sources = self._result_context(
            session,
            output_uid=current.uid,
        )
        if context_record_digest(current) != context_record_digest(expected):
            return None
        checkpoints = self.store.list_checkpoints(session.output_name)
        if len(checkpoints) != 1:
            return None
        checkpoint = checkpoints[0]
        expected_args = self._checkpoint_args(session, expected, sources)
        expected_sever = expected_args.get("sever")
        legacy_args = (
            {
                **expected_args,
                "sever": {
                    key: value
                    for key, value in expected_sever.items()
                    if key != "save_mode"
                },
            }
            if isinstance(expected_sever, dict)
            else expected_args
        )
        if (
            checkpoint.get("command") != "sever"
            or checkpoint.get("args") not in (expected_args, legacy_args)
            or not isinstance(checkpoint.get("uid"), str)
        ):
            return None
        return session.with_application(
            SeverApplication(
                output_context_uid=current.uid,
                checkpoint_uid=checkpoint["uid"],
                result_memory_uids=result_uids,
            )
        )

    def _recover_self_save(self, session: SeverSession) -> SeverSession | None:
        """Adopt an exact self-save committed before its session receipt."""

        current = self.store.load_direct(session.output_name)
        for checkpoint in self.store.list_checkpoints(session.output_name):
            before = checkpoint.get("command_before")
            snapshot = checkpoint.get("snapshot")
            if (
                checkpoint.get("command") != "sever"
                or not isinstance(checkpoint.get("uid"), str)
                or not isinstance(before, dict)
                or not isinstance(snapshot, dict)
            ):
                continue
            try:
                original = Context.from_dict(before)
                expected, result_uids, sources = self._self_save_context(
                    session,
                    original,
                )
            except (SeverApplicationError, TypeError, ValueError):
                continue
            if (
                checkpoint.get("args")
                != self._checkpoint_args(session, expected, sources)
                or context_record_digest(snapshot) != context_record_digest(expected)
                or current.uid != expected.uid
                or context_record_digest(current) != context_record_digest(expected)
            ):
                continue
            return session.with_application(
                SeverApplication(
                    output_context_uid=current.uid,
                    checkpoint_uid=checkpoint["uid"],
                    result_memory_uids=result_uids,
                )
            )
        return None

    def materialize(self, session: SeverSession) -> SeverSession:
        granted_bindings = tuple(
            (label, binding)
            for label, binding in (
                ("Source", session.source),
                ("Criteria", session.criteria),
            )
            if binding.granted is not None
        )
        if not granted_bindings:
            return self._materialize_frozen(session)

        # Freeze the grant registry across both validation passes and output
        # creation. The second pass makes the Result's commit point observe
        # the exact authority content captured by the reviewed session.
        with authority_grant_snapshot_lock() as registry:
            for label, binding in granted_bindings:
                self._revalidate_granted_binding(label, binding, registry)
            applied = self._materialize_frozen(session)
            try:
                for label, binding in granted_bindings:
                    self._revalidate_granted_binding(label, binding, registry)
            except Exception:
                self.rollback_materialization(applied)
                raise
            return applied

    def _revalidate_granted_binding(
        self,
        label: str,
        binding: SeverContextBinding,
        registry: ProfileRegistry,
    ) -> None:
        if binding.granted is None:
            raise SeverApplicationError(
                f"The Sever {label} is not a granted input."
            )
        frozen = GrantedUpdateTarget.from_dict(binding.granted)
        try:
            access = revalidate_granted_context_binding(
                frozen,
                required_permission="READ",
                registry=registry,
                active_store=self.store,
            )
            current = capture_sever_binding(
                access,
                include_descendants=binding.include_descendants,
                registry=registry,
            )
        except (FileNotFoundError, ProfileError, ValueError) as error:
            raise SeverApplicationError(
                f"The granted Sever {label} is no longer authorized for Apply."
            ) from error
        if current != binding:
            raise SeverApplicationError(
                f"The granted Sever {label} changed after review. Re-run Sever."
            )

    def _materialize_frozen(self, session: SeverSession) -> SeverSession:
        if session.save_mode == "SELF_SAVE":
            return self._materialize_self_save(session)
        output, result_uids, sources = self._result_context(
            session,
            output_uid=str(uuid.uuid4()),
        )

        local_bindings: list[tuple[str, str, str]] = []
        for binding in (session.source, session.criteria):
            if binding.granted is None:
                local_bindings.extend(binding.contexts)
        deduplicated = tuple(dict.fromkeys(local_bindings))
        auto_checkpoint = AutoCheckpoint(
            command="sever",
            args=self._checkpoint_args(session, output, sources),
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
                result_memory_uids=result_uids,
            )
        )

    def _materialize_self_save(self, session: SeverSession) -> SeverSession:
        """Replace one exact Source root with its reviewed Sever projection."""

        original = self.store.load_direct(session.output_name)
        output, result_uids, sources = self._self_save_context(session, original)
        checkpoint_args = self._checkpoint_args(session, output, sources)
        auto_checkpoint = AutoCheckpoint(
            command="sever",
            args=checkpoint_args,
            description=(
                f"Self-saved Sever result into '{session.output_name}' under "
                f"'{session.criteria.root_name}': "
                f"{len(result_uids)} kept, "
                f"{len(session.candidates) - len(result_uids)} forgotten"
            ),
        )
        criteria_bindings = (
            session.criteria.contexts
            if session.criteria.granted is None
            else ()
        )
        if criteria_bindings:
            checkpoint = self.store.save_context_with_sources(
                output,
                auto_checkpoint,
                expected_context_digest=context_record_digest(original),
                source_bindings=criteria_bindings,
            )
        else:
            checkpoint = self.store.save(
                output,
                auto_checkpoint,
                expected_context_digest=context_record_digest(original),
            )
        if checkpoint is None:
            raise SeverApplicationError("Sever self-save produced no checkpoint.")
        return session.with_application(
            SeverApplication(
                output_context_uid=output.uid,
                checkpoint_uid=checkpoint.uid,
                result_memory_uids=result_uids,
            )
        )

    def rollback_materialization(self, applied: SeverSession) -> None:
        """Compensate only the exact save named by an uncommitted receipt."""

        application = applied.application
        if applied.state != "APPLIED" or application is None:
            raise SeverApplicationError(
                "Only an applied Sever receipt can roll back its Result."
            )
        if applied.save_mode == "SELF_SAVE":
            self._rollback_self_save(applied)
            return
        expected = Context(
            uid=application.output_context_uid,
            name=applied.output_name,
        )
        expected_uids: list[str] = []
        for _candidate, source, content in applied.results():
            uid = _result_uid(applied.uid, source.uid, content)
            expected.add(Memory(uid=uid, content=content))
            expected_uids.append(uid)
        if tuple(expected_uids) != application.result_memory_uids:
            raise SeverApplicationError(
                "The Sever receipt does not identify its exact Result Memories."
            )
        expected_digest = context_record_digest(expected)

        # This is compensation for an outcome that never committed, not a
        # user-visible deletion. Hold the same Store boundaries as creation
        # and intentionally avoid publishing a lifecycle event.
        with self.store._command_write_lock():  # noqa: SLF001
            with self.store._context_graph_lock(exclusive=False):  # noqa: SLF001
                with self.store._context_write_lock(applied.output_name):  # noqa: SLF001
                    with self.store.profile_write_guard():
                        current = self.store.load_direct(applied.output_name)
                        if (
                            current.uid != application.output_context_uid
                            or context_record_digest(current) != expected_digest
                        ):
                            raise SeverApplicationError(
                                "The new Sever Result changed before rollback."
                            )
                        checkpoints = self.store.list_checkpoints(applied.output_name)
                        if (
                            len(checkpoints) != 1
                            or checkpoints[0].get("uid")
                            != application.checkpoint_uid
                        ):
                            raise SeverApplicationError(
                                "The new Sever Result checkpoint changed before "
                                "rollback."
                            )
                        self.store._delete_locked(applied.output_name)  # noqa: SLF001

    def _rollback_self_save(self, applied: SeverSession) -> None:
        """Restore the exact Source pre-image after failed session persistence."""

        application = applied.application
        if application is None:
            raise SeverApplicationError("Self-save rollback requires an application.")
        reviewed = replace(
            applied,
            revision=applied.revision - 1,
            state="REVIEWING",
            application=None,
        )
        with self.store._command_write_lock():  # noqa: SLF001
            with self.store._context_graph_lock(exclusive=False):  # noqa: SLF001
                with self.store._context_write_lock(applied.output_name):  # noqa: SLF001
                    with self.store.profile_write_guard():
                        current = self.store.load_direct(applied.output_name)
                        checkpoint = next(
                            (
                                item
                                for item in self.store.list_checkpoints(
                                    applied.output_name
                                )
                                if item.get("uid") == application.checkpoint_uid
                            ),
                            None,
                        )
                        before = (
                            checkpoint.get("command_before")
                            if isinstance(checkpoint, dict)
                            else None
                        )
                        snapshot = (
                            checkpoint.get("snapshot")
                            if isinstance(checkpoint, dict)
                            else None
                        )
                        if not isinstance(before, dict) or not isinstance(snapshot, dict):
                            raise SeverApplicationError(
                                "The self-save checkpoint cannot restore its Source."
                            )
                        original = Context.from_dict(before)
                        expected, result_uids, sources = self._self_save_context(
                            reviewed,
                            original,
                        )
                        if (
                            application.result_memory_uids != result_uids
                            or current.uid != application.output_context_uid
                            or context_record_digest(current)
                            != context_record_digest(expected)
                            or context_record_digest(snapshot)
                            != context_record_digest(expected)
                            or checkpoint.get("args")
                            != self._checkpoint_args(
                                reviewed,
                                expected,
                                sources,
                            )
                        ):
                            raise SeverApplicationError(
                                "The self-saved Sever Result changed before rollback."
                            )
                        _write_json_atomic(
                            self.store._context_file(applied.output_name),  # noqa: SLF001
                            before,
                        )
                        self.store._remove_checkpoint_uid_locked(  # noqa: SLF001
                            applied.output_name,
                            application.checkpoint_uid,
                        )


def execute_sever_apply(
    request: SeverApplyRequest,
    *,
    store: MemoryStore,
) -> SeverApplyResult:
    """Apply one exact review through the production save-location port."""

    return run_sever_apply(
        request,
        output_port=MemoryStoreSeverOutputPort(store),
    )


def execute_sever_session_start(
    analysis: SeverAnalysisResult,
    *,
    store: MemoryStore,
) -> SeverStoredAnalysisResult:
    """Persist one newly analyzed review through the private session adapter."""

    return run_sever_session_start(
        analysis,
        repository=MemoryStoreSeverSessionRepository(store),
    )


def execute_sever_session_open(
    uid: str,
    *,
    store: MemoryStore,
) -> SeverSessionSnapshot:
    """Load one exact saved session without terminal or interface behavior."""

    return run_sever_session_open(
        uid,
        repository=MemoryStoreSeverSessionRepository(store),
    )


def execute_sever_session_decision(
    request: SeverDecisionRequest,
    *,
    store: MemoryStore,
) -> SeverSessionSnapshot:
    """Persist one reviewed candidate decision under session CAS."""

    return run_sever_session_decision(
        request,
        repository=MemoryStoreSeverSessionRepository(store),
    )


def execute_sever_session_destination_change(
    request: SeverDestinationRequest,
    *,
    store: MemoryStore,
) -> SeverSessionSnapshot:
    """Validate and persist one self- or other-save destination revision."""

    session = request.snapshot.session
    return run_sever_session_destination_change(
        request,
        repository=MemoryStoreSeverSessionRepository(store),
        destination_port=MemoryStoreSeverDestinationPort(
            store,
            source_name=session.source.root_name,
            self_save_allowed=(
                session.source.granted is None
                and not session.source.include_descendants
            ),
        ),
    )


def execute_sever_session_apply(
    request: SeverPersistedApplyRequest,
    *,
    store: MemoryStore,
) -> SeverPersistedApplyResult:
    """Materialize and persist one saved review through the lifecycle boundary."""

    return run_sever_session_apply(
        request,
        repository=MemoryStoreSeverSessionRepository(store),
        output_port=MemoryStoreSeverOutputPort(store),
    )
