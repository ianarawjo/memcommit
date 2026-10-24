"""Production Store and provider composition for the Summarize use case."""

from __future__ import annotations


from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Protocol

from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
)
from memcommit.models.context import Context
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.summarize.model import (
    SummarizeError,
    SummarizeProvider,
    SummaryFrame,
    collect_summary_scope,
)
from memcommit.application.operations.summarize.application import (
    FrozenSummarySource,
    SummarizeRequest,
    SummarizeResult,
    SummaryProviderSessionFactory,
    SummarySourcePort,
    run_summarize,
)


class SummaryProviderFactory(Protocol):
    """Construct the already-configured provider for one nonempty request."""

    def __call__(self) -> SummarizeProvider:
        """Return a provider without introducing terminal presentation."""


@dataclass(frozen=True)
class _StoreSummarySourceToken:
    """Opaque source binding retained between freeze and revalidation."""

    context_identities: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _LoadedSummaryScope:
    """One unified readable scope plus every authority binding it used."""

    frame: SummaryFrame
    context_identities: tuple[tuple[str, str], ...]


def _load_frame(
    active_store: MemoryStore,
    access,
    *,
    include_descendants: bool,
) -> _LoadedSummaryScope:
    store = ReadableContextCatalog(
        active_store,
        access,
    )
    root_name = access.access_name
    catalog_names = store.list_context_names(sort_order="alphabetical")
    names = (
        list_context_and_descendant_names((root_name,), catalog_names)
        if include_descendants
        else (root_name,)
    )
    load = store.load_direct
    contexts = tuple(load(name) for name in names)
    context_identities: list[tuple[str, str]] = []
    visited_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited_contexts:
            return
        visited_contexts.add(context.uid)
        context_identities.append((context.name, context.uid))

    for context in contexts:
        visit(context)

    return _LoadedSummaryScope(
        frame=collect_summary_scope(
            contexts,
            root_context_uid=contexts[0].uid,
            root_context_name=root_name,
            include_descendants=include_descendants,
        ),
        context_identities=tuple(context_identities),
    )


class MemoryStoreSummarySourcePort(SummarySourcePort):
    """Freeze and revalidate one local MemoryStore source scope."""

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
        access = resolve_existing_context_access(
            self._store,
            request.context_locator,
            current_name=self._current_name,
        ).value
        loaded = _load_frame(
            self._store,
            access,
            include_descendants=request.include_descendants,
        )
        return FrozenSummarySource(
            frame=loaded.frame,
            token=_StoreSummarySourceToken(
                context_identities=loaded.context_identities,
            ),
        )

    def revalidate(self, source: FrozenSummarySource) -> SummaryFrame:
        token = source.token
        if not isinstance(token, _StoreSummarySourceToken):
            raise SummarizeError("The frozen summary source binding is invalid.")
        access = resolve_context_access(
            self._store,
            source.frame.context_name,
            current_name=self._current_name,
        )
        loaded = _load_frame(
            self._store,
            access,
            include_descendants=source.frame.include_descendants,
        )
        if loaded.context_identities != token.context_identities:
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
