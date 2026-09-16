"""Assemble a Rationale report from existing evidence and optional inference."""

from __future__ import annotations

from typing import Callable

from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
)
from memcommit.application.operations.rationale.evidence_collection import (
    _context_candidates,
    _fallback_evidence,
    _origin_events,
    _proposal_evidence,
    _provenance_character_budget,
    _recorded_reason_events,
    _saved_analysis,
    _target_state,
)
from memcommit.application.operations.rationale.model import (
    ContextEvidence,
    ContextInference,
    RationaleProvider,
    RationaleReport,
)
from memcommit.application.operations.rationale.runtime import run_context_inference
from memcommit.application.operations.rationale.skills.context_inference import (
    _inference_character_budget,
)
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore


def build_rationale(
    store: MemoryStore,
    ctx: Context,
    trace: MemoryHistory,
    provider_factory: Callable[[], RationaleProvider] | None,
    *,
    cache_inference: bool = False,
    refresh_inference: bool = False,
    inference_contexts: tuple[Context, ...] | None = None,
    inference_scope_name: str | None = None,
    inference_scope_include_descendants: bool = False,
    recorded_evidence_available: bool = True,
) -> RationaleReport:
    """Combine live durable evidence with an optional contextual reading."""
    target = _target_state(trace)
    if recorded_evidence_available:
        saved_analysis, stale_analysis, review_warnings = _saved_analysis(
            store,
            ctx,
            trace,
        )
        proposals, proposal_warnings = _proposal_evidence(store, ctx, trace)
    else:
        saved_analysis = None
        stale_analysis = False
        proposals = ()
        review_warnings = []
        proposal_warnings = []
    inference_contexts = inference_contexts or (ctx,)
    # A provenance-only caller must not inspect neighboring Memories merely to
    # populate dormant inference diagnostics. Candidate work begins only when
    # an explicit provider factory establishes a semantic inference boundary.
    if provider_factory is None:
        candidates: tuple[ContextEvidence, ...] = ()
        limited = False
        fallback: tuple[ContextEvidence, ...] = ()
    else:
        candidates, limited = _context_candidates(inference_contexts, target)
        fallback = _fallback_evidence(candidates)
    if recorded_evidence_available:
        provenance_source_character_count, provenance_character_limit = (
            _provenance_character_budget(trace)
        )
    else:
        provenance_source_character_count = 0
        provenance_character_limit = 0
    if provider_factory is None:
        inference_source_character_count = 0
        inference_character_limit = 0
    else:
        inference_source_character_count, inference_character_limit = (
            _inference_character_budget(target, candidates, saved_analysis)
        )
    warnings = [*review_warnings, *proposal_warnings]
    if limited:
        warnings.append(
            "The Context exceeded the one-shot rationale input limit; "
            "inference used an explicit nearest-Memory subset."
        )

    inference: ContextInference | None = None
    inference_cached = False
    inference_error: str | None = None
    inference_status = "NOT_REQUESTED"
    if provider_factory is not None:
        (
            inference,
            inference_cached,
            inference_error,
            inference_status,
            inference_warnings,
        ) = run_context_inference(
            store,
            ctx,
            target,
            candidates,
            saved_analysis,
            provider_factory,
            limited=limited,
            inference_contexts=inference_contexts,
            recorded_evidence_available=recorded_evidence_available,
            cache_inference=cache_inference,
            refresh_inference=refresh_inference,
            inference_source_character_count=inference_source_character_count,
            inference_character_limit=inference_character_limit,
        )
        warnings.extend(inference_warnings)

    return RationaleReport(
        trace=trace,
        target=target,
        origin_events=_origin_events(trace),
        recorded_reason_events=_recorded_reason_events(trace),
        saved_analysis=saved_analysis,
        stale_analysis=stale_analysis,
        proposals=proposals,
        inference=inference,
        inference_cached=inference_cached,
        fallback_evidence=fallback,
        inference_error=inference_error,
        warnings=tuple(warnings),
        inference_scope_name=inference_scope_name or ctx.name,
        inference_scope_context_count=len(inference_contexts),
        inference_scope_include_descendants=inference_scope_include_descendants,
        recorded_evidence_available=recorded_evidence_available,
        provenance_source_character_count=provenance_source_character_count,
        provenance_character_limit=provenance_character_limit,
        inference_source_character_count=inference_source_character_count,
        inference_character_limit=inference_character_limit,
        inference_status=inference_status,
    )
