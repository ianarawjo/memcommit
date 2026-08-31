"""Production Store and provider composition for the Summarize use case."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Protocol

# Transitional dependency: these operation-neutral Grant mechanics predate the
# application boundary and still live under commands. Keep the dependency in
# this infrastructure adapter so the application and domain remain terminal-
# independent; move it only after another vertical slice proves the same owner.
from memcommit.application.capabilities.authority.context_access import (
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.authority.readable_contexts import ReadableContextCatalog
from memcommit.core.context import Context
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.operations.profiles.profile.model import authority_grant_snapshot_lock
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.search_explain.synthesize.summarize.model import (
    SummarizeError,
    SummarizeProvider,
    SummaryFrame,
    collect_summary_scope,
)
from memcommit.application.operations.search_explain.synthesize.summarize.application import (
    FrozenSummarySource,
    SummarizeRequest,
    SummarizeResult,
    SummaryProviderSessionFactory,
    SummarySourcePort,
    run_summarize,
)
from memcommit.study_scenarios.legacy.prewarm.summarize import (
    find_declared_summarize_prewarm,
)
from memcommit.application.operations.semantic_updates.foundation.update.model import GrantedUpdateTarget


class SummaryProviderFactory(Protocol):
    """Construct the already-configured provider for one nonempty request."""

    def __call__(self) -> SummarizeProvider:
        """Return a provider without introducing terminal presentation."""


@dataclass(frozen=True)
class _StoreSummarySourceToken:
    """Opaque source binding retained between freeze and revalidation."""

    context_identities: tuple[tuple[str, str], ...]
    granted_bindings: tuple[GrantedUpdateTarget, ...]


@dataclass(frozen=True)
class _LoadedSummaryScope:
    """One unified readable scope plus every authority binding it used."""

    frame: SummaryFrame
    context_identities: tuple[tuple[str, str], ...]
    granted_bindings: tuple[GrantedUpdateTarget, ...]


def _load_frame(
    active_store: MemoryStore,
    access,
    *,
    include_descendants: bool,
    follow_embeds: bool,
    registry=None,
) -> _LoadedSummaryScope:
    # A recursive public namespace can mix ordinary local Contexts and
    # READ-granted Contexts.  Freeze one catalog so lexical expansion, loading,
    # and later Grant revalidation all use the same public-name bindings.
    store = ReadableContextCatalog(
        active_store,
        access,
        registry=registry,
        include_query_routes=False,
    )
    root_name = access.display_name
    names = expand_lexical_context_names(
        ContextScope.create(
            (root_name,),
            include_descendants=include_descendants,
        ),
        sorted(store.list_context_names(), key=str.casefold),
    )
    # A local catalog row may project attached READ grants as marker-free child
    # Contexts for browsing. Summary cannot carry those contributors into its
    # authority token, so provider-facing recursive loads omit that implicit
    # edge; an explicitly selected granted public name remains loadable here.
    load = store.load_without_attached_reads if follow_embeds else store.load_direct
    contexts = tuple(load(name) for name in names)
    context_identities: list[tuple[str, str]] = []
    visited_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited_contexts:
            return
        visited_contexts.add(context.uid)
        context_identities.append((context.name, context.uid))
        if follow_embeds:
            for item in context.iter_items():
                if isinstance(item, Context):
                    visit(item)

    for context in contexts:
        visit(context)

    granted_bindings = tuple(
        freeze_granted_context_binding(selected_access)
        for name in names
        if (selected_access := store.access_for(name)).is_granted
    )
    return _LoadedSummaryScope(
        frame=collect_summary_scope(
            contexts,
            root_context_uid=contexts[0].uid,
            root_context_name=root_name,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
        ),
        context_identities=tuple(context_identities),
        granted_bindings=granted_bindings,
    )


class MemoryStoreSummarySourcePort(SummarySourcePort):
    """Freeze and revalidate one real local or granted MemoryStore source."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        # The active Context is process-global mutable state. Capture it once
        # so every relative lookup in this request has one stable base.
        self._current_name = current_name

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreSummarySourcePort":
        """Create a source adapter from one current-Context snapshot."""

        return cls(store, current_name=store.current_context_name())

    def freeze(self, request: SummarizeRequest) -> FrozenSummarySource:
        with authority_grant_snapshot_lock() as registry:
            access = resolve_context_access(
                self._store,
                request.context_locator,
                current_name=self._current_name,
                required_permission="READ",
                registry=registry,
            )
            loaded = _load_frame(
                self._store,
                access,
                include_descendants=request.include_descendants,
                follow_embeds=request.follow_embeds,
                registry=registry,
            )
        return FrozenSummarySource(
            frame=loaded.frame,
            token=_StoreSummarySourceToken(
                context_identities=loaded.context_identities,
                granted_bindings=loaded.granted_bindings,
            ),
        )

    def revalidate(self, source: FrozenSummarySource) -> SummaryFrame:
        token = source.token
        if not isinstance(token, _StoreSummarySourceToken):
            raise SummarizeError("The frozen summary source binding is invalid.")
        with authority_grant_snapshot_lock() as registry:
            for binding in token.granted_bindings:
                revalidate_granted_context_binding(
                    binding,
                    registry=registry,
                    active_store=self._store,
                )
            access = resolve_context_access(
                self._store,
                source.frame.context_name,
                current_name=self._current_name,
                required_permission="READ",
                registry=registry,
            )
            loaded = _load_frame(
                self._store,
                access,
                include_descendants=source.frame.include_descendants,
                follow_embeds=source.frame.follow_embeds,
                registry=registry,
            )
        if (
            loaded.context_identities != token.context_identities
            or loaded.granted_bindings != token.granted_bindings
        ):
            raise SummarizeError(
                "The selected readable Context scope changed while "
                "summarization was running; no summary was published."
            )
        return loaded.frame


def run_summarize_with_store(
    request: SummarizeRequest,
    *,
    store: MemoryStore,
    current_context_name: str | None,
    provider_session_factory: SummaryProviderSessionFactory,
) -> SummarizeResult:
    """Compose the application with a real Store and an injected session."""

    return run_summarize(
        request,
        source_port=MemoryStoreSummarySourcePort(
            store,
            current_name=current_context_name,
        ),
        provider_session_factory=provider_session_factory,
        prepared_lookup=lambda frame: find_declared_summarize_prewarm(
            store=store,
            frame=frame,
        ),
    )


def execute_summarize(
    request: SummarizeRequest,
    *,
    store: MemoryStore,
    provider_factory: SummaryProviderFactory,
) -> SummarizeResult:
    """Execute against a real Store with no CLI, TUI, or terminal output."""

    @contextmanager
    def provider_session() -> Iterator[SummarizeProvider]:
        # This closure is intentionally lazy: run_summarize opens it only after
        # READ authorization and only when the frozen frame is nonempty.
        yield provider_factory()

    return run_summarize_with_store(
        request,
        store=store,
        current_context_name=store.current_context_name(),
        provider_session_factory=provider_session,
    )
