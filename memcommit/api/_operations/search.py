"""Public application assembly for provider-backed semantic Search."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.semantic import safe_semantic_provider
from memcommit.api.errors import (
    SemanticAuthorityError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.api.search import SearchItemResult, SearchResult
from memcommit.authority.access import ContextAccess, resolve_context_access
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
    freeze_readable_context_catalog,
)
from memcommit.find_application import (
    FindSearchRequest,
    FindSearchResponse,
)
from memcommit.find_runtime import execute_find_search
from memcommit.history import HistoryError
from memcommit.history_search import HistorySearchError
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError, authority_grant_snapshot_lock
from memcommit.search import FindError
from memcommit.store import MemoryStore


class _LocalReadableCatalog:
    """Keep an explicitly rooted client isolated from global Profile grants."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def list_context_names(self) -> list[str]:
        return self._store.list_context_names()

    def context_exists(self, name: str) -> bool:
        return self._store.context_exists(name)

    def load_direct(self, name: str):
        return self._store.load_direct(name)

    def load(self, name: str):
        return self._store.load(name)

    def access_for(self, name: str) -> ContextAccess:
        if not self._store.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' is outside the view.")
        return ContextAccess(
            store=self._store,
            context_name=name,
            display_name=name,
            attachment_name=None,
            permission="READ",
        )


def _current_name(runtime: ClientRuntime) -> str | None:
    try:
        return runtime.store.current_context_name()
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise_public(SemanticStorageError, error)


def _active_registry(runtime: ClientRuntime):
    """Return only the registry that actually owns this client's Store."""

    if runtime.registry is None or runtime.profile is None:
        return None
    try:
        registry = load_profile_registry()
        if (
            registry.active.uid != runtime.profile.uid
            or runtime.store_root != profile_store_dir(registry.active).resolve()
        ):
            return None
        return registry
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
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


def _public(response: FindSearchResponse) -> SearchResult:
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
        request = FindSearchRequest(
            query=query,
            target_names=targets,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            limit=limit,
        )
        configured_registry = _active_registry(runtime)
        if configured_registry is None:
            if any(not runtime.store.context_exists(name) for name in targets):
                raise FileNotFoundError(
                    "Explicit-root Search can read only Contexts in its own Store."
                )
            catalog = _LocalReadableCatalog(runtime.store)
        else:
            # Resolve every operand against the same current snapshot and one
            # Grant revision. Provider construction stays downstream of this
            # freeze, so rejected scopes cannot disclose content by connecting.
            with authority_grant_snapshot_lock() as live_registry:
                accesses = tuple(
                    resolve_context_access(
                        runtime.store,
                        name,
                        current_name=current_name,
                        required_permission="READ",
                        registry=live_registry,
                    )
                    for name in targets
                )
                if len(accesses) > 1:
                    catalog = freeze_profile_readable_context_catalog(
                        runtime.store,
                        accesses[0],
                        include_query_routes=follow_embeds,
                    )
                    for access in accesses:
                        catalog.access_for(access.display_name)
                else:
                    catalog = freeze_readable_context_catalog(
                        runtime.store,
                        accesses[0],
                        include_query_routes=follow_embeds,
                    )
        response = execute_find_search(
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
    except (FindError, HistoryError, HistorySearchError, RuntimeError) as error:
        raise_public(SemanticExecutionError, error)


__all__ = ["search"]
