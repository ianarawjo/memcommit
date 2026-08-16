"""Public Query route assembly without a dependency on the client facade."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.errors import (
    QueryAuthorityError,
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
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError
from memcommit.query_sessions import QuerySessionError
from memcommit.search import FindError


StageObserver = Callable[[str], None]


def _current_context_name(runtime: ClientRuntime) -> str | None:
    store = runtime.store
    if not store.state_file.exists():
        return None
    try:
        return store.current_context_name()
    except (OSError, ValueError) as error:
        raise_public(QueryStorageError, error)


def _safe_ordinary_provider(runtime: ClientRuntime) -> object:
    try:
        return runtime.ordinary_provider_factory()
    except QueryProviderFailure:
        raise
    except Exception as error:
        raise_public(QueryProviderFailure, error)


def _safe_route_provider(runtime: ClientRuntime, provider_name: str) -> object:
    try:
        return runtime.query_route_provider_factory(provider_name)
    except QueryProviderFailure:
        raise
    except Exception as error:
        raise_public(QueryProviderFailure, error)


def query_ordinary(
    runtime: ClientRuntime,
    question: str,
    *,
    context_names: Sequence[str] | None = None,
    include_descendants: bool = False,
    follow_embeds: bool = True,
    on_stage: StageObserver | None = None,
) -> OrdinaryQueryResult:
    """Answer from one exact readable Context set without publishing state."""

    store = runtime.store
    current_name = _current_context_name(runtime)
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
            raise_public(QueryInputError, error)
        if not operands:
            raise QueryInputError("Select at least one readable Context.")

    accesses = []
    try:
        for operand in operands:
            if not isinstance(operand, str) or not operand:
                raise ValueError("Context names must be nonblank text.")
            canonical = resolve_context_locator(operand, current=current_name)
            # An explicit Store root is intentionally local-only. It must not
            # inherit host grants merely because an attachment matches.
            if runtime.registry is None and not store.context_exists(canonical):
                raise FileNotFoundError(f"Context {canonical!r} not found.")
            accesses.append(
                resolve_context_access(
                    store,
                    operand,
                    current_name=current_name,
                    required_permission="READ",
                    registry=runtime.registry,
                )
            )
        catalog = freeze_profile_readable_context_catalog(store, accesses[0])
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
        raise_public(QueryContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(QueryAuthorityError, error)
    except (TypeError, ValueError) as error:
        raise_public(QueryInputError, error)

    try:
        response = execute_ordinary_query(
            request,
            store=store,
            catalog=catalog,
            provider_factory=lambda: _safe_ordinary_provider(runtime),
            observer=on_stage,  # type: ignore[arg-type]
        )
    except QueryProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(QueryProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(QueryContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(QueryAuthorityError, error)
    except OSError as error:
        raise_public(QueryStorageError, error)
    except (
        FindAnswerCorpusTooLarge,
        OrdinaryQueryCorpusTooLarge,
        FindError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        raise_public(QueryExecutionError, error)

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
    runtime: ClientRuntime,
    public_name: str,
    question: str | None = None,
    *,
    language: str = "en",
    session_name: str | None = None,
    memory_handle: str | None = None,
    federate_descendants: bool = True,
    on_stage: StageObserver | None = None,
) -> GrantedQueryResult:
    """Browse or answer one active-Profile QUERY grant."""

    store = runtime.store
    try:
        if not isinstance(public_name, str) or not public_name:
            raise ValueError("Granted Query public name must be nonblank.")
        registry = load_profile_registry()
        if (
            runtime.profile is None
            or runtime.profile.uid != registry.active.uid
            or runtime.store_root != profile_store_dir(registry.active).resolve()
        ):
            raise QueryAuthorityError(
                "Granted Query requires a client bound to the active Profile."
            )
        targets = freeze_granted_query_targets(store)
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
        raise_public(QueryAuthorityError, error)
    except (QuerySessionError, TypeError, ValueError) as error:
        raise_public(QueryInputError, error)
    except OSError as error:
        raise_public(QueryStorageError, error)

    try:
        outcome = execute_granted_query_read(
            request,
            store=store,
            provider_factory=lambda: _safe_ordinary_provider(runtime),
            observer=on_stage,  # type: ignore[arg-type]
        )
    except QueryProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(QueryProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(QueryContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(QueryAuthorityError, error)
    except QuerySessionError as error:
        raise_public(QueryExecutionError, error)
    except OSError as error:
        raise_public(QueryStorageError, error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(QueryExecutionError, error)

    receipt = None
    if outcome.publication is not None:
        try:
            published = execute_granted_query_session_publication(
                outcome.publication,
                store=store,
                observer=on_stage,  # type: ignore[arg-type]
            )
        except (ProfileConfigError, ProfileError, QuerySessionError) as error:
            raise_public(QueryPublicationError, error)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise_public(QueryPublicationError, error)
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
    runtime: ClientRuntime,
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
        raise_public(QueryInputError, error)
    try:
        response = execute_query_reference(
            request,
            store=runtime.store,
            provider_factory=lambda name: _safe_route_provider(runtime, name),
            observer=on_stage,  # type: ignore[arg-type]
        )
    except QueryProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(QueryProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(QueryContextError, error)
    except OSError as error:
        raise_public(QueryStorageError, error)
    except (RuntimeError, TypeError, ValueError) as error:
        raise_public(QueryExecutionError, error)
    return ReferenceQueryResult(
        source_name=response.request.source_name,
        answer=response.answer,
    )


__all__ = ["query_granted", "query_ordinary", "query_reference"]

