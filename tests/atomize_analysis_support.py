"""Test-only convenience adapter for the canonical Atomize analysis boundary."""

from __future__ import annotations

from typing import Callable

from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisOpenRequest,
    AtomizeAnalysisOpenResult,
)
from memcommit.application.operations.atomize.analysis_runtime import (
    ATOMIZE_AGGREGATE_TIMEOUT_SECONDS,
    _connect_aggregate_atomize_provider,
    execute_atomize_analysis_open,
)
from memcommit.application.operations.atomize.domain import (
    AtomizeAnalysisSession,
    AtomizeFrameOrigin,
    AtomizeProvider,
)
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore


def open_or_create_atomize_review_record(
    *,
    store: MemoryStore,
    ctx: Context,
    provider_factory: Callable[[], AtomizeProvider],
    refresh: bool = False,
    declared_frames: dict[str, str] | None = None,
    declared_frame_origins: dict[str, AtomizeFrameOrigin] | None = None,
    source_review_uid: str | None = None,
    source_review_digest: str | None = None,
    output_context_name: str | None = None,
    validate_before_save: Callable[[], None] | None = None,
    prepared_analysis: AtomizeAnalysisSession | None = None,
    memory_selector: str | None = None,
) -> AtomizeAnalysisOpenResult:
    """Keep test setup concise while exercising the production typed boundary."""

    return execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(
            context=ctx,
            refresh=refresh,
            declared_frames=declared_frames,
            declared_frame_origins=declared_frame_origins,
            source_review_uid=source_review_uid,
            source_review_digest=source_review_digest,
            output_context_name=output_context_name,
            memory_selector=memory_selector,
            allow_prepared=prepared_analysis is not None and not refresh,
        ),
        store=store,
        provider_factory=provider_factory,
        validate_before_save=validate_before_save,
        prepared_analysis_override=prepared_analysis,
        prepared_output_name=output_context_name,
    )


__all__ = [
    "ATOMIZE_AGGREGATE_TIMEOUT_SECONDS",
    "_connect_aggregate_atomize_provider",
    "open_or_create_atomize_review_record",
]
