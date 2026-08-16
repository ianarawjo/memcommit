"""Stable Python entry point over reviewed MemCommit application boundaries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
from pathlib import Path

from memcommit.api.add import (
    AddMemoriesResult,
    AddedMemoryResult,
)
from memcommit.api.errors import (
    AddAuthorityError,
    AddConflictError,
    AddContextError,
    AddExecutionError,
    AddInputError,
    AddStorageError,
    MeldAuthorityError,
    MeldConflictError,
    MeldContextError,
    MeldExecutionError,
    MeldInputError,
    MeldProviderFailure,
    MeldStorageError,
    QueryAuthorityError,
    QueryConfigurationError,
    QueryContextError,
    QueryExecutionError,
    QueryInputError,
    QueryProviderFailure,
    QueryPublicationError,
    QueryStorageError,
)
from memcommit.api.meld import (
    MeldApplyResult as PublicMeldApplyResult,
    MeldIssueResult,
    MeldOptionResult,
    MeldProposalResult,
    MeldSessionResult,
)
from memcommit.api.query import (
    GrantedQueryResult,
    OrdinaryQueryResult,
    QueryCatalogEntry,
    QueryCitation,
    QueryProviderConfig,
    QuerySessionReceipt,
    ReferenceQueryResult,
)
from memcommit.context import QueryContextRef
from memcommit.profile_config import (
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


ProviderFactory = Callable[[], object]
RouteProviderFactory = Callable[[str], object]
StageObserver = Callable[[str], None]


_UNLOADED_INTEGRATION = object()

# These names remain patchable without eagerly importing their implementations.
# The loaders replace only this sentinel, so an injected test or host adapter wins.
run_add = _UNLOADED_INTEGRATION
execute_granted_query_session_publication = _UNLOADED_INTEGRATION
execute_meld_start = _UNLOADED_INTEGRATION
execute_meld_restart = _UNLOADED_INTEGRATION


def _publish_integration(namespace: dict[str, object]) -> None:
    for name, value in namespace.items():
        if name.startswith("_"):
            continue
        if globals().get(name, _UNLOADED_INTEGRATION) is _UNLOADED_INTEGRATION:
            globals()[name] = value


def _load_add_integration() -> None:
    """Load Add's application/runtime assembly only when Add is selected."""

    from memcommit.add_application import (
        AddError as ApplicationAddError,
        AddRequest,
        AddSource,
        run_add,
        validate_add_request,
    )
    from memcommit.add_runtime import MemoryStoreAddTargetPort
    from memcommit.context_locator import resolve_context_locator
    from memcommit.store import ConcurrentContextUpdateError

    _publish_integration(locals())


def _load_meld_integration() -> None:
    """Load Meld's durable review assembly only when a Meld method is used."""

    from memcommit.authority.access import resolve_context_access
    from memcommit.context_locator import resolve_context_locator
    from memcommit.meld import (
        MELD_SCHEMA_VERSION,
        MeldError as CoreMeldError,
        meld_canonical_digest,
    )
    from memcommit.meld_application import MeldApplyRequest
    from memcommit.meld_provider import MeldProviderError
    from memcommit.meld_restart_application import MeldRestartError, MeldRestartRequest
    from memcommit.meld_runtime import (
        execute_meld_apply,
        execute_meld_assessment,
        execute_meld_preservation,
        execute_meld_restart,
        execute_meld_session_defer,
        execute_meld_session_open,
        execute_meld_start,
        load_meld_source,
        prepare_meld_assessment,
    )
    from memcommit.meld_session_application import (
        MeldTurnRequest,
        prepare_meld_preservation_turn,
        prepare_meld_turn,
    )
    from memcommit.meld_start_application import MeldStartError, MeldStartRequest
    from memcommit.store import ConcurrentContextUpdateError

    _publish_integration(locals())


def _load_query_integration() -> None:
    """Load Query authority/runtime assembly only when Query is selected."""

    from memcommit.authority.access import resolve_context_access
    from memcommit.context_locator import resolve_context_locator
    from memcommit.context_targeting.readable_catalog import (
        freeze_profile_readable_context_catalog,
    )
    from memcommit.find_answer_dialogue import FindAnswerCorpusTooLarge
    from memcommit.operations.query.granted_application import (
        GrantedQueryRequest,
        GrantedQueryTarget,
    )
    from memcommit.operations.query.granted_runtime import (
        execute_granted_query_read,
        execute_granted_query_session_publication,
        freeze_granted_query_targets,
    )
    from memcommit.operations.query.ordinary_application import OrdinaryQueryRequest
    from memcommit.operations.query.ordinary_runtime import execute_ordinary_query
    from memcommit.operations.query.reference_application import QueryReferenceRequest
    from memcommit.operations.query.reference_runtime import execute_query_reference
    from memcommit.ordinary_query_answer import OrdinaryQueryCorpusTooLarge
    from memcommit.query_provider import QueryProviderError
    from memcommit.query_sessions import QuerySessionError
    from memcommit.search import FindError

    _publish_integration(locals())


def _raise(error_type: type[Exception], error: BaseException) -> None:
    raise error_type(str(error)) from error


class MemCommitClient:
    """Own one frozen Store boundary and provider configuration snapshot.

    Provider objects remain per-call resources. The client itself owns no open
    endpoint or terminal resource and therefore requires no explicit close.
    """

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        profile: str | None = None,
        create: bool = False,
        query_config: QueryProviderConfig | None = None,
        ordinary_provider_factory: ProviderFactory | None = None,
        query_route_provider_factory: RouteProviderFactory | None = None,
        semantic_provider_factory: ProviderFactory | None = None,
    ) -> None:
        if root is not None and profile is not None:
            raise QueryConfigurationError(
                "Choose either an explicit Store root or a Profile, not both."
            )
        if not isinstance(create, bool):
            raise QueryConfigurationError("Client create must be a boolean.")
        try:
            config = query_config or QueryProviderConfig()
        except (TypeError, ValueError) as error:
            _raise(QueryConfigurationError, error)
        if not isinstance(config, QueryProviderConfig):
            raise QueryConfigurationError("query_config must be a QueryProviderConfig.")

        registry: ProfileRegistry | None = None
        selected_profile: ProfileEntry | None = None
        try:
            if root is None:
                registry = load_profile_registry()
                if profile is None:
                    selected_profile = registry.active
                else:
                    selected_profile = registry.by_name(profile)
                    if selected_profile is None or registry.is_removed(
                        selected_profile
                    ):
                        raise QueryConfigurationError(
                            f"Profile {profile!r} is not available."
                        )
                store_root = profile_store_dir(selected_profile)
            else:
                store_root = Path(root).expanduser().absolute()
        except QueryConfigurationError:
            raise
        except (OSError, ProfileConfigError, TypeError, ValueError) as error:
            _raise(QueryConfigurationError, error)

        self._store = MemoryStore(root=store_root, create=create)
        self._store_root = self._store.store_dir.resolve()
        self._registry = registry
        self._profile = selected_profile
        self._query_config = config
        self._ordinary_provider_factory = (
            ordinary_provider_factory or self._connect_ordinary_provider
        )
        self._query_route_provider_factory = (
            query_route_provider_factory or self._connect_route_provider
        )
        self._semantic_provider_factory = (
            semantic_provider_factory or self._connect_ordinary_provider
        )

    @property
    def store_root(self) -> Path:
        return self._store_root

    @property
    def profile_name(self) -> str | None:
        return self._profile.name if self._profile is not None else None

    @property
    def query_config(self) -> QueryProviderConfig:
        return self._query_config

    def _connect_ordinary_provider(self) -> object:
        from memcommit.infrastructure.providers.find_query import (
            connect_ordinary_query_provider,
        )

        config = self._query_config
        return connect_ordinary_query_provider(
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            timeout_seconds=config.timeout_seconds,
        )

    def _connect_route_provider(self, provider_name: str) -> object:
        from memcommit.infrastructure.providers.find_query import (
            connect_query_route_provider,
        )

        config = self._query_config
        return connect_query_route_provider(
            provider_name,
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            timeout_seconds=config.timeout_seconds,
        )

    def _safe_ordinary_provider(self) -> object:
        try:
            return self._ordinary_provider_factory()
        except QueryProviderFailure:
            raise
        except Exception as error:
            _raise(QueryProviderFailure, error)

    def _safe_route_provider(self, provider_name: str) -> object:
        try:
            return self._query_route_provider_factory(provider_name)
        except QueryProviderFailure:
            raise
        except Exception as error:
            _raise(QueryProviderFailure, error)

    def _safe_semantic_provider(self) -> object:
        try:
            return self._semantic_provider_factory()
        except MeldProviderFailure:
            raise
        except Exception as error:
            _raise(MeldProviderFailure, error)

    @staticmethod
    def _project_meld(session, *, origin: str | None = None) -> MeldSessionResult:
        _load_meld_integration()
        assessment = session.current_assessment
        application = session.application
        return MeldSessionResult(
            session_uid=session.uid,
            version=meld_canonical_digest(session.to_dict()),
            mode=session.mode,
            state=session.state,
            left_context=session.frames[0].context_name,
            right_context=session.frames[1].context_name,
            target_context=session.target.context_name,
            turn_count=len(session.turns),
            overview=assessment.overview if assessment is not None else None,
            ready_to_apply=(
                assessment.ready_to_apply if assessment is not None else False
            ),
            issues=(
                tuple(
                    MeldIssueResult(
                        uid=issue.uid,
                        priority=issue.priority,
                        title=issue.title,
                        question=issue.question,
                        why_it_matters=issue.why_it_matters,
                        options=tuple(
                            MeldOptionResult(
                                uid=option.uid,
                                label=option.label,
                                text=option.text,
                            )
                            for option in issue.options
                        ),
                    )
                    for issue in assessment.issues
                )
                if assessment is not None
                else ()
            ),
            proposals=(
                tuple(
                    MeldProposalResult(
                        uid=proposal.uid,
                        operation=proposal.operation,
                        disposition=proposal.disposition,
                        content=proposal.content,
                        reason=proposal.reason,
                    )
                    for proposal in assessment.proposals
                )
                if assessment is not None
                else ()
            ),
            origin=origin,
            checkpoint_uid=(
                application.checkpoint_uid if application is not None else None
            ),
        )

    def _meld_snapshot(self, target_name: str):
        _load_meld_integration()
        current_name = self._current_context_name()
        canonical = resolve_context_locator(target_name, current=current_name)
        access = resolve_context_access(
            self._store,
            canonical,
            current_name=current_name,
            required_permission="READ",
        )
        target = load_meld_source(access, project=False)
        return execute_meld_session_open(target.uid, store=self._store)

    def start_meld(
        self,
        left_context: str,
        right_context: str,
        *,
        mode: str = "directional",
        target_context: str | None = None,
        create_target: bool = False,
        left_descendants: bool = False,
        right_descendants: bool = False,
    ) -> MeldSessionResult:
        """Create one durable reviewed Meld without opening a terminal UI."""

        _load_meld_integration()
        try:
            if mode not in {"directional", "symmetric"}:
                raise ValueError("mode must be directional or symmetric.")
            if any(
                not isinstance(value, str) or not value.strip()
                for value in (left_context, right_context)
            ):
                raise ValueError("Meld source names must be nonblank text.")
            if not isinstance(create_target, bool) or not isinstance(
                left_descendants,
                bool,
            ) or not isinstance(right_descendants, bool):
                raise TypeError("Meld scope and creation controls must be booleans.")
            current_name = self._current_context_name()
            left = resolve_context_locator(left_context, current=current_name)
            right = resolve_context_locator(right_context, current=current_name)
            if mode == "directional":
                if target_context is not None and target_context != right:
                    raise ValueError("Directional target must be the BASELINE.")
                target = right
            else:
                if target_context is None:
                    raise ValueError("Symmetric Meld requires target_context.")
                target = (
                    target_context
                    if create_target
                    else resolve_context_locator(
                        target_context,
                        current=current_name,
                    )
                )
            request = MeldStartRequest(
                mode=mode.upper(),  # type: ignore[arg-type]
                left_name=left,
                right_name=right,
                target_name=target,
                left_descendants=left_descendants,
                right_descendants=right_descendants,
                create_target=create_target,
            )
        except (TypeError, ValueError, CoreMeldError, MeldStartError) as error:
            _raise(MeldInputError, error)
        try:
            result = execute_meld_start(
                request,
                store=self._store,
                provider_factory=self._safe_semantic_provider,
            )
        except MeldProviderFailure:
            raise
        except MeldProviderError as error:
            _raise(MeldProviderFailure, error)
        except FileNotFoundError as error:
            _raise(MeldContextError, error)
        except ProfileError as error:
            _raise(MeldAuthorityError, error)
        except ConcurrentContextUpdateError as error:
            _raise(MeldConflictError, error)
        except OSError as error:
            _raise(MeldStorageError, error)
        except (CoreMeldError, MeldStartError, RuntimeError, TypeError, ValueError) as error:
            _raise(MeldExecutionError, error)
        return self._project_meld(result.session, origin=result.origin)

    def restart_meld(
        self,
        left_context: str,
        right_context: str,
        target_context: str,
        *,
        expected_version: str,
        mode: str = "directional",
        left_descendants: bool = False,
        right_descendants: bool = False,
    ) -> MeldSessionResult:
        """Replace one exact saved Meld review without deleting its target."""

        _load_meld_integration()
        try:
            if mode not in {"directional", "symmetric"}:
                raise ValueError("mode must be directional or symmetric.")
            if any(
                not isinstance(value, str) or not value.strip()
                for value in (
                    left_context,
                    right_context,
                    target_context,
                    expected_version,
                )
            ):
                raise ValueError(
                    "Meld restart names and expected_version must be nonblank text."
                )
            if not isinstance(left_descendants, bool) or not isinstance(
                right_descendants,
                bool,
            ):
                raise TypeError("Meld scope controls must be booleans.")
            current_name = self._current_context_name()
            left = resolve_context_locator(left_context, current=current_name)
            right = resolve_context_locator(right_context, current=current_name)
            target = resolve_context_locator(target_context, current=current_name)
            if mode == "directional" and target != right:
                raise ValueError("Directional target must be the BASELINE.")
            request = MeldRestartRequest(
                mode=mode.upper(),  # type: ignore[arg-type]
                left_name=left,
                right_name=right,
                target_name=target,
                expected_version=expected_version,
                left_descendants=left_descendants,
                right_descendants=right_descendants,
            )
        except (TypeError, ValueError, CoreMeldError, MeldRestartError) as error:
            _raise(MeldInputError, error)
        try:
            result = execute_meld_restart(
                request,
                store=self._store,
                provider_factory=self._safe_semantic_provider,
            )
        except MeldProviderFailure:
            raise
        except MeldProviderError as error:
            _raise(MeldProviderFailure, error)
        except FileNotFoundError as error:
            _raise(MeldContextError, error)
        except ProfileError as error:
            _raise(MeldAuthorityError, error)
        except ConcurrentContextUpdateError as error:
            _raise(MeldConflictError, error)
        except OSError as error:
            _raise(MeldStorageError, error)
        except (
            CoreMeldError,
            MeldRestartError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            _raise(MeldExecutionError, error)
        return self._project_meld(result.session, origin=result.origin)

    def open_meld(self, target_context: str) -> MeldSessionResult:
        """Open one exact saved review without provider or mutation."""

        try:
            snapshot = self._meld_snapshot(target_context)
        except FileNotFoundError as error:
            _raise(MeldContextError, error)
        except ProfileError as error:
            _raise(MeldAuthorityError, error)
        except OSError as error:
            _raise(MeldStorageError, error)
        except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
            _raise(MeldExecutionError, error)
        return self._project_meld(snapshot.session)

    def comment_meld(
        self,
        target_context: str,
        comment: str,
        *,
        issue_uid: str | None = None,
        revision: str = "EXTEND",
        revises_turn_uids: Sequence[str] = (),
    ) -> MeldSessionResult:
        """Submit one complete semantic follow-up against a saved version."""

        try:
            if not isinstance(comment, str) or not comment.strip():
                raise ValueError("comment must be nonblank text.")
            snapshot = self._meld_snapshot(target_context)
            pending = prepare_meld_turn(
                MeldTurnRequest(
                    snapshot=snapshot,
                    comment=comment,
                    scope="ISSUE" if issue_uid is not None else "ALL",
                    issue_uids=(issue_uid,) if issue_uid is not None else (),
                    revision=revision.upper(),  # type: ignore[arg-type]
                    revises_turn_uids=tuple(revises_turn_uids),
                )
            )
            frozen, port = prepare_meld_assessment(
                pending.session,
                store=self._store,
                expected_session_digest=pending.expected_version,
            )
            result = execute_meld_assessment(
                frozen,
                port=port,
                provider_factory=self._safe_semantic_provider,
            )
        except MeldProviderFailure:
            raise
        except MeldProviderError as error:
            _raise(MeldProviderFailure, error)
        except FileNotFoundError as error:
            _raise(MeldContextError, error)
        except ProfileError as error:
            _raise(MeldAuthorityError, error)
        except ConcurrentContextUpdateError as error:
            _raise(MeldConflictError, error)
        except OSError as error:
            _raise(MeldStorageError, error)
        except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
            _raise(MeldExecutionError, error)
        return self._project_meld(result.session, origin=result.origin)

    def preserve_meld(self, target_context: str) -> MeldSessionResult:
        """Preserve every remaining distinction under the saved-session CAS."""

        try:
            snapshot = self._meld_snapshot(target_context)
            pending = prepare_meld_preservation_turn(
                snapshot,
                guidance=(
                    "Preserve every remaining supported source distinction "
                    "without inventing unsupported content."
                ),
            )
            session = pending.session
            if session.mode == "SYMMETRIC" and session.schema_version >= MELD_SCHEMA_VERSION:
                saved = execute_meld_preservation(pending, store=self._store)
                return self._project_meld(saved.session, origin="LOCAL")
            frozen, port = prepare_meld_assessment(
                session,
                store=self._store,
                expected_session_digest=pending.expected_version,
            )
            result = execute_meld_assessment(
                frozen,
                port=port,
                provider_factory=self._safe_semantic_provider,
            )
        except MeldProviderFailure:
            raise
        except MeldProviderError as error:
            _raise(MeldProviderFailure, error)
        except FileNotFoundError as error:
            _raise(MeldContextError, error)
        except ProfileError as error:
            _raise(MeldAuthorityError, error)
        except ConcurrentContextUpdateError as error:
            _raise(MeldConflictError, error)
        except OSError as error:
            _raise(MeldStorageError, error)
        except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
            _raise(MeldExecutionError, error)
        return self._project_meld(result.session, origin=result.origin)

    def defer_meld(self, target_context: str) -> MeldSessionResult:
        """Close one saved review without changing its target."""

        try:
            snapshot = self._meld_snapshot(target_context)
            saved = execute_meld_session_defer(snapshot, store=self._store)
        except FileNotFoundError as error:
            _raise(MeldContextError, error)
        except ConcurrentContextUpdateError as error:
            _raise(MeldConflictError, error)
        except OSError as error:
            _raise(MeldStorageError, error)
        except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
            _raise(MeldExecutionError, error)
        return self._project_meld(saved.session, origin="LOCAL")

    def apply_meld(self, target_context: str) -> PublicMeldApplyResult:
        """Apply exactly one ready saved proposal without another provider turn."""

        try:
            snapshot = self._meld_snapshot(target_context)
            applied = execute_meld_apply(
                MeldApplyRequest(
                    session=snapshot.session,
                    expected_session_digest=snapshot.version_token,
                ),
                store=self._store,
            )
        except FileNotFoundError as error:
            _raise(MeldContextError, error)
        except ProfileError as error:
            _raise(MeldAuthorityError, error)
        except ConcurrentContextUpdateError as error:
            _raise(MeldConflictError, error)
        except OSError as error:
            _raise(MeldStorageError, error)
        except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
            _raise(MeldExecutionError, error)
        return PublicMeldApplyResult(
            session=self._project_meld(applied.session, origin="LOCAL"),
            recovered=applied.receipt.recovered,
            checkpoint_uid=applied.receipt.checkpoint_uid,
            result_count=applied.receipt.result_count,
        )

    def _current_context_name(self) -> str | None:
        if not self._store.state_file.exists():
            return None
        try:
            return self._store.current_context_name()
        except (OSError, ValueError) as error:
            _raise(QueryStorageError, error)

    def add_memories(
        self,
        contents: Sequence[str],
        *,
        context_name: str | None = None,
    ) -> AddMemoriesResult:
        """Append one exact ordered batch and publish one Add checkpoint."""

        _load_add_integration()
        try:
            if isinstance(contents, (str, bytes)):
                raise TypeError("contents must be a sequence of Memory texts.")
            values = tuple(contents)
            if context_name is not None and (
                not isinstance(context_name, str) or not context_name
            ):
                raise ValueError("context_name must be nonblank text.")
            request = validate_add_request(
                AddRequest(
                    contents=values,
                    context_locator=context_name,
                    source=AddSource(
                        mode="EXPLICIT_BATCH",
                        kind="python-api",
                        parser="exact-memory-sequence-v1",
                        raw_text=json.dumps(
                            values,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    ),
                )
            )
        except (ApplicationAddError, TypeError, ValueError) as error:
            _raise(AddInputError, error)

        try:
            current_name = (
                self._store.current_context_name()
                if self._store.state_file.exists()
                else None
            )
            operand = context_name or current_name
            if operand is None:
                raise FileNotFoundError(
                    "No current Context; pass context_name or initialize one."
                )
            canonical = resolve_context_locator(operand, current=current_name)
            target_is_local = self._store.context_exists(canonical)
            if not target_is_local:
                if self._registry is None:
                    raise FileNotFoundError(f"Context {canonical!r} not found.")
                registry = load_profile_registry()
                if (
                    self._profile is None
                    or self._profile.uid != registry.active.uid
                    or self._store_root != profile_store_dir(registry.active).resolve()
                ):
                    raise AddAuthorityError(
                        "CREATE-granted Add requires a client bound to the "
                        "active Profile."
                    )
            port = MemoryStoreAddTargetPort(
                self._store,
                current_name=current_name,
                local_only=target_is_local,
            )
            result = run_add(request, target_port=port)
        except AddAuthorityError:
            raise
        except FileNotFoundError as error:
            _raise(AddContextError, error)
        except (ProfileConfigError, ProfileError) as error:
            _raise(AddAuthorityError, error)
        except ConcurrentContextUpdateError as error:
            _raise(AddConflictError, error)
        except OSError as error:
            _raise(AddStorageError, error)
        except (ApplicationAddError, RuntimeError, TypeError, ValueError) as error:
            _raise(AddExecutionError, error)

        return AddMemoriesResult(
            context_name=result.context_name,
            context_uid=result.context_uid,
            memories=tuple(
                AddedMemoryResult(uid=memory.uid, content=memory.content)
                for memory in result.memories
            ),
            checkpoint_uid=result.checkpoint_uid,
        )

    def query_ordinary(
        self,
        question: str,
        *,
        context_names: Sequence[str] | None = None,
        include_descendants: bool = False,
        follow_embeds: bool = True,
        on_stage: StageObserver | None = None,
    ) -> OrdinaryQueryResult:
        """Answer from one exact readable Context set without publishing state."""

        _load_query_integration()
        current_name = self._current_context_name()
        operands: tuple[str, ...]
        if context_names is None:
            if current_name is None:
                raise QueryContextError(
                    "No current Context; pass context_names or initialize one."
                )
            operands = (current_name,)
        elif isinstance(context_names, (str, bytes)):
            raise QueryInputError("context_names must be a sequence of names.")
        else:
            try:
                operands = tuple(context_names)
            except TypeError as error:
                _raise(QueryInputError, error)
            if not operands:
                raise QueryInputError("Select at least one readable Context.")

        accesses = []
        try:
            for operand in operands:
                if not isinstance(operand, str) or not operand:
                    raise ValueError("Context names must be nonblank text.")
                canonical = resolve_context_locator(operand, current=current_name)
                # An explicit Store root is intentionally local-only. It must
                # not inherit host grants merely because an attachment matches.
                if self._registry is None and not self._store.context_exists(canonical):
                    raise FileNotFoundError(f"Context {canonical!r} not found.")
                accesses.append(
                    resolve_context_access(
                        self._store,
                        operand,
                        current_name=current_name,
                        required_permission="READ",
                        registry=self._registry,
                    )
                )
            catalog = freeze_profile_readable_context_catalog(
                self._store,
                accesses[0],
            )
            target_names = tuple(access.display_name for access in accesses)
            if any(not catalog.context_exists(name) for name in target_names):
                raise ProfileError(
                    "A selected Context left the frozen readable Profile view."
                )
            request = OrdinaryQueryRequest(
                question=question,
                target_names=target_names,
                include_descendants=include_descendants,
                follow_embeds=follow_embeds,
            )
        except FileNotFoundError as error:
            _raise(QueryContextError, error)
        except (ProfileConfigError, ProfileError) as error:
            _raise(QueryAuthorityError, error)
        except (TypeError, ValueError) as error:
            _raise(QueryInputError, error)

        try:
            response = execute_ordinary_query(
                request,
                store=self._store,
                catalog=catalog,
                provider_factory=self._safe_ordinary_provider,
                observer=on_stage,  # type: ignore[arg-type]
            )
        except QueryProviderFailure:
            raise
        except QueryProviderError as error:
            _raise(QueryProviderFailure, error)
        except FileNotFoundError as error:
            _raise(QueryContextError, error)
        except (ProfileConfigError, ProfileError) as error:
            _raise(QueryAuthorityError, error)
        except OSError as error:
            _raise(QueryStorageError, error)
        except (
            FindAnswerCorpusTooLarge,
            OrdinaryQueryCorpusTooLarge,
            FindError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            _raise(QueryExecutionError, error)

        citations = ()
        if response.reference_document is not None:
            citations = tuple(
                QueryCitation(
                    number=item.number,
                    alias=item.evidence.alias,
                    context_name=item.evidence.context_name,
                    kind=item.evidence.kind,
                    uid=item.evidence.uid,
                    content=item.evidence.content,
                )
                for item in response.reference_document.references
            )
        return OrdinaryQueryResult(
            answer=response.answer,
            grounded=response.grounded,
            citations=citations,
        )

    def query_granted(
        self,
        public_name: str,
        question: str | None = None,
        *,
        language: str = "en",
        session_name: str | None = None,
        memory_handle: str | None = None,
        federate_descendants: bool = True,
        on_stage: StageObserver | None = None,
    ) -> GrantedQueryResult:
        """Browse or answer one active-Profile QUERY grant.

        When ``session_name`` is supplied, returning successfully means the
        visible turn was also reauthorized and CAS-published.
        """

        _load_query_integration()
        try:
            if not isinstance(public_name, str) or not public_name:
                raise ValueError("Granted Query public name must be nonblank.")
            registry = load_profile_registry()
            if (
                self._profile is None
                or self._profile.uid != registry.active.uid
                or self._store_root != profile_store_dir(registry.active).resolve()
            ):
                raise QueryAuthorityError(
                    "Granted Query requires a client bound to the active Profile."
                )
            targets = freeze_granted_query_targets(self._store)
            matches = tuple(
                target
                for target in targets
                if public_name == target.public_name
                or public_name.startswith(target.public_name + "/")
            )
            if not matches:
                raise QueryContextError(
                    f"Query-only view {public_name!r} is not available."
                )
            base_target = max(
                matches,
                key=lambda target: len(target.public_name.split("/")),
            )
            if session_name is not None and not base_target.session_log_allowed:
                raise QueryAuthorityError(
                    f"Query-only view {public_name!r} does not allow SESSION_LOG."
                )
            request = GrantedQueryRequest(
                target=GrantedQueryTarget(
                    grant_uid=base_target.grant_uid,
                    public_name=public_name,
                    attachment_name=base_target.attachment_name,
                    session_log_allowed=base_target.session_log_allowed,
                ),
                question=question,
                language=language,
                session_name=session_name,
                memory_handle=memory_handle,
                federate_descendants=federate_descendants,
            )
        except (QueryAuthorityError, QueryContextError):
            raise
        except (ProfileConfigError, ProfileError) as error:
            _raise(QueryAuthorityError, error)
        except (QuerySessionError, TypeError, ValueError) as error:
            _raise(QueryInputError, error)
        except OSError as error:
            _raise(QueryStorageError, error)

        try:
            outcome = execute_granted_query_read(
                request,
                store=self._store,
                provider_factory=self._safe_ordinary_provider,
                observer=on_stage,  # type: ignore[arg-type]
            )
        except QueryProviderFailure:
            raise
        except QueryProviderError as error:
            _raise(QueryProviderFailure, error)
        except FileNotFoundError as error:
            _raise(QueryContextError, error)
        except (ProfileConfigError, ProfileError) as error:
            _raise(QueryAuthorityError, error)
        except QuerySessionError as error:
            _raise(QueryExecutionError, error)
        except OSError as error:
            _raise(QueryStorageError, error)
        except (RuntimeError, TypeError, ValueError) as error:
            _raise(QueryExecutionError, error)

        receipt = None
        if outcome.publication is not None:
            try:
                published = execute_granted_query_session_publication(
                    outcome.publication,
                    store=self._store,
                    observer=on_stage,  # type: ignore[arg-type]
                )
            except (ProfileConfigError, ProfileError, QuerySessionError) as error:
                _raise(QueryPublicationError, error)
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                _raise(QueryPublicationError, error)
            receipt = QuerySessionReceipt(
                session_name=published.session_name,
                revision=published.revision,
                turn_count=published.turn_count,
            )

        response = outcome.response
        if response.answer is None:
            return GrantedQueryResult(
                mode="CATALOG",
                public_name=public_name,
                catalog=tuple(
                    QueryCatalogEntry(entry.handle, entry.placeholder_lines)
                    for entry in response.catalog
                ),
            )
        return GrantedQueryResult(
            mode="ANSWER",
            public_name=public_name,
            answer=response.answer,
            session_receipt=receipt,
        )

    def query_reference(
        self,
        reference: QueryContextRef,
        question: str,
        *,
        language: str = "en",
        on_stage: StageObserver | None = None,
    ) -> ReferenceQueryResult:
        """Answer through one exact legacy QueryContextRef without persistence."""

        _load_query_integration()
        try:
            if not isinstance(reference, QueryContextRef):
                raise TypeError("reference must be a QueryContextRef.")
            request = QueryReferenceRequest(
                source_uid=reference.target_source_uid,
                source_name=reference.name,
                provider_name=reference.provider,
                question=question,
                language=language,
            )
        except (TypeError, ValueError) as error:
            _raise(QueryInputError, error)
        try:
            response = execute_query_reference(
                request,
                store=self._store,
                provider_factory=self._safe_route_provider,
                observer=on_stage,  # type: ignore[arg-type]
            )
        except QueryProviderFailure:
            raise
        except QueryProviderError as error:
            _raise(QueryProviderFailure, error)
        except FileNotFoundError as error:
            _raise(QueryContextError, error)
        except OSError as error:
            _raise(QueryStorageError, error)
        except (RuntimeError, TypeError, ValueError) as error:
            _raise(QueryExecutionError, error)
        return ReferenceQueryResult(
            source_name=response.request.source_name,
            answer=response.answer,
        )


__all__ = ["MemCommitClient"]
