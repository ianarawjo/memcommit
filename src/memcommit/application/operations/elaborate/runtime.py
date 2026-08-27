"""Operation-owned provider composition for Elaborate generation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Protocol

from memcommit.application.operations.elaborate.model import ElaborateProvider, ElaborateTargetContext
from memcommit.application.operations.elaborate.application import (
    ElaboratePreparedLookup,
    ElaborateRequest,
    ElaborateResult,
    run_elaborate,
)
from memcommit.application.operations.elaborate.config import (
    DEFAULT_ELABORATE_SEMANTIC_CONFIG,
    ElaborateSemanticConfig,
)


class ElaborateProviderFactory(Protocol):
    def __call__(self) -> ElaborateProvider:
        """Construct one configured provider lazily."""


def execute_elaborate(
    request: ElaborateRequest,
    *,
    provider_factory: ElaborateProviderFactory,
    config: ElaborateSemanticConfig = DEFAULT_ELABORATE_SEMANTIC_CONFIG,
    prepared_lookup: ElaboratePreparedLookup | None = None,
    target_context: ElaborateTargetContext | None = None,
) -> ElaborateResult:
    """Execute without importing CLI, TUI, Ground, or storage adapters."""

    @contextmanager
    def provider_session() -> Iterator[ElaborateProvider]:
        yield provider_factory()

    return run_elaborate(
        request,
        provider_session_factory=provider_session,
        config=config,
        prepared_lookup=prepared_lookup,
        target_context=target_context,
    )


__all__ = ["ElaborateProviderFactory", "execute_elaborate"]
