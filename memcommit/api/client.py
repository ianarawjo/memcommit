"""Stable Python entry point over reviewed MemCommit application boundaries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
from pathlib import Path

from memcommit.add_application import (
    AddError as ApplicationAddError,
    AddRequest,
    AddSource,
    run_add,
    validate_add_request,
)
from memcommit.add_runtime import MemoryStoreAddTargetPort
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
    QueryAuthorityError,
    QueryConfigurationError,
    QueryContextError,
    QueryExecutionError,
    QueryInputError,
    QueryProviderFailure,
    QueryPublicationError,
    QueryStorageError,
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
from memcommit.authority.access import resolve_context_access
from memcommit.context import QueryContextRef
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.find_answer_dialogue import FindAnswerCorpusTooLarge
from memcommit.infrastructure.providers.find_query import (
    connect_ordinary_query_provider,
    connect_query_route_provider,
)
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
from memcommit.profile_config import (
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError
from memcommit.query_sessions import QuerySessionError
from memcommit.search import FindError
from memcommit.store import MemoryStore
from memcommit.store import ConcurrentContextUpdateError


ProviderFactory = Callable[[], object]
RouteProviderFactory = Callable[[str], object]
StageObserver = Callable[[str], None]


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
        config = self._query_config
        return connect_ordinary_query_provider(
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            timeout_seconds=config.timeout_seconds,
        )

    def _connect_route_provider(self, provider_name: str) -> object:
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
