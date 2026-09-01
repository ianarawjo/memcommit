"""Public application assembly for provider-backed semantic Search."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api._support.readable import (
    freeze_client_readable_catalog,
)
from memcommit.adapters.python_api._support.semantic import safe_semantic_provider
from memcommit.adapters.python_api.errors import (
    SemanticAuthorityError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.adapters.python_api.search import SearchItemResult, SearchResult
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.search.application import (
    SearchRequest,
    SearchResponse,
)
from memcommit.application.operations.search.runtime import execute_search
from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import HistoryError
from memcommit.application.capabilities.history.query.semantic_history_query import HistorySearchError
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.search.errors import SearchError


def _current_name(runtime: ClientRuntime) -> str | None:
    try:
        return runtime.store.current_context_name()
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise_public(SemanticStorageError, error)


def _canonical_targets(
    runtime: ClientRuntime,
    context_names: Sequence[str],
    *,
    current_name: str | None,
) -> tuple[str, ...]:
    if isinstance(context_names, (str, bytes)):
        raise TypeError("Search Context names must be a sequence.")
    operands = tuple(context_names)
    if not operands:
        if current_name is None:
            raise FileNotFoundError("No current Context is available.")
        operands = (current_name,)
    if any(not isinstance(name, str) or not name.strip() for name in operands):
        raise TypeError("Search Context names must be nonblank text.")
    canonical = tuple(
        resolve_context_locator(name, current=current_name) for name in operands
    )
    if len(set(canonical)) != len(canonical):
        raise ValueError("Search Context names must not repeat.")
    return canonical


def _public(response: SearchResponse) -> SearchResult:
    request = response.request
    return SearchResult(
        query=request.query,
        context_names=request.target_names,
        include_descendants=request.include_descendants,
        follow_embeds=request.follow_embeds,
        mode=response.mode,
        items=tuple(
            SearchItemResult(
                context_name=item.context_name,
                kind=item.kind,
                uid=item.uid,
                content=item.content,
                relevance=item.relevance,
                source_context_name=item.source_context_name,
                source_context_uid=item.source_context_uid,
                source_memory_uid=item.source_memory_uid,
            )
            for item in response.results
        ),
        related_query=response.related_query,
    )


def search(
    runtime: ClientRuntime,
    query: str,
    context_names: Sequence[str] = (),
    *,
    include_descendants: bool = False,
    follow_embeds: bool = False,
    limit: int = 5,
) -> SearchResult:
    """Search one frozen readable scope without terminal or mutation effects."""

    try:
        current_name = _current_name(runtime)
        targets = _canonical_targets(
            runtime,
            context_names,
            current_name=current_name,
        )
        request = SearchRequest(
            query=query,
            target_names=targets,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            limit=limit,
        )
        catalog = freeze_client_readable_catalog(
            runtime,
            targets,
            current_name=current_name,
            include_query_routes=follow_embeds,
        )
        response = execute_search(
            request,
            store=runtime.store,
            catalog=catalog,
            provider_factory=lambda: safe_semantic_provider(runtime),
        )
        return _public(response)
    except (SemanticAuthorityError, SemanticProviderFailure):
        raise
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    except (SearchError, HistoryError, HistorySearchError, RuntimeError) as error:
        raise_public(SemanticExecutionError, error)


__all__ = ["search"]
