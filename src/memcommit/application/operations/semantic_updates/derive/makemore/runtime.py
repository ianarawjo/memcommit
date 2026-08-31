"""Operation-owned provider composition for Makemore generation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Protocol

from memcommit.application.operations.semantic_updates.derive.makemore.model import MakemoreProvider, MakemoreTargetContext
from memcommit.application.operations.semantic_updates.derive.makemore.application import (
    MakemorePreparedLookup,
    MakemoreRequest,
    MakemoreResult,
    run_makemore,
)
from memcommit.application.operations.semantic_updates.derive.makemore.config import (
    DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
    MakemoreSemanticConfig,
)


class MakemoreProviderFactory(Protocol):
    def __call__(self) -> MakemoreProvider:
        """Construct one configured provider lazily."""


def execute_makemore(
    request: MakemoreRequest,
    *,
    provider_factory: MakemoreProviderFactory,
    config: MakemoreSemanticConfig = DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
    prepared_lookup: MakemorePreparedLookup | None = None,
    target_context: MakemoreTargetContext | None = None,
) -> MakemoreResult:
    """Execute without importing CLI, TUI, Ground, or storage adapters."""

    @contextmanager
    def provider_session() -> Iterator[MakemoreProvider]:
        yield provider_factory()

    return run_makemore(
        request,
        provider_session_factory=provider_session,
        config=config,
        prepared_lookup=prepared_lookup,
        target_context=target_context,
    )


__all__ = ["MakemoreProviderFactory", "execute_makemore"]
