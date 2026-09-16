"""Store-backed optional inference and retained-history preparation for Rationale."""

from __future__ import annotations

from typing import Callable

from memcommit.application.capabilities.history.query.context_history_slicing import (
    ContextHistorySlice,
    build_context_history_slice,
    current_context_history_slice,
)
from memcommit.application.capabilities.history.verification import MemoryState
from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.operations.rationale.cache import (
    load_rationale_inference,
    rationale_inference_input_digest,
    save_rationale_inference,
)
from memcommit.application.operations.rationale.model import (
    ContextEvidence,
    ContextInference,
    RationaleError,
    RationaleEvidenceTooSmall,
    RationaleProvider,
    SavedAnalysis,
)
from memcommit.application.operations.rationale.skills.context_inference import (
    _cache_record,
    _cached_inference,
    _inference_request,
    _parse_inference,
)
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.providers.subscription import QueryProviderError


def load_context_rationale_history(
    store: MemoryStore,
    context_name: str,
    *,
    current_context_name: str | None,
) -> tuple[ContextHistorySlice, bool]:
    """Prepare the existing exact Context route without opening granted history."""

    access = resolve_context_access(
        store,
        context_name,
        current_name=current_context_name,
        required_permission="READ",
    )
    report = (
        current_context_history_slice(
            access.store.load_direct(access.context_name),
            warnings=("Authority history is outside this granted READ view.",),
        )
        if access.is_granted
        else build_context_history_slice(access.store, access.context_name)
    )
    return report, not access.is_granted


def run_context_inference(
    store: MemoryStore,
    ctx: Context,
    target: MemoryState,
    candidates: list[ContextEvidence],
    saved_analysis: SavedAnalysis | None,
    provider_factory: Callable[[], RationaleProvider],
    *,
    limited: bool,
    inference_contexts: tuple[Context, ...],
    recorded_evidence_available: bool,
    cache_inference: bool,
    refresh_inference: bool,
    inference_source_character_count: int,
    inference_character_limit: int,
) -> tuple[ContextInference | None, bool, str | None, str, list[str]]:
    """Run the pre-existing optional inference with its exact cache publication checks."""

    warnings: list[str] = []
    inference: ContextInference | None = None
    inference_cached = False
    inference_error: str | None = None
    inference_status = "UNAVAILABLE"
    try:
        (
            prompt,
            output_schema,
            request_source_character_count,
            request_character_limit,
        ) = _inference_request(
            target=target,
            candidates=candidates,
            analysis=saved_analysis,
            limited=limited,
        )
        if (
            request_source_character_count != inference_source_character_count
            or request_character_limit != inference_character_limit
        ):
            raise RationaleError(
                "Rationale inference character budget changed during planning."
            )
        input_digest: str | None = None
        # A subtree cache needs a multi-Context publication transaction.
        # Until that exists, keep recursive and granted inference ephemeral
        # rather than publishing a result after validating only one owner.
        cache_enabled = (
            cache_inference
            and recorded_evidence_available
            and len(inference_contexts) == 1
        )
        if cache_enabled:
            try:
                input_digest = rationale_inference_input_digest(
                    context_uid=ctx.uid,
                    selected_memory_uid=target.uid,
                    prompt=prompt,
                    output_schema=output_schema,
                )
            except (OSError, RuntimeError, ValueError):
                cache_enabled = False
                warnings.append(
                    "Rationale inference caching is unavailable for this "
                    "Context or Memory identity."
                )
        if cache_enabled and input_digest is not None and not refresh_inference:
            try:
                cached = load_rationale_inference(
                    ctx.uid,
                    target.uid,
                    input_digest,
                )
            except (OSError, RuntimeError, ValueError):
                warnings.append(
                    "Saved rationale inference cache was invalid or "
                    "unavailable and was ignored."
                )
            else:
                if cached is not None:
                    try:
                        inference = _cached_inference(
                            cached,
                            candidates,
                            explanation_character_limit=(inference_character_limit),
                        )
                    except RationaleError:
                        warnings.append(
                            "Saved rationale inference cache was invalid "
                            "and was ignored."
                        )
                    else:
                        inference_cached = True

        if inference is None:
            provider = provider_factory()
            raw = provider.complete(
                prompt,
                operation="rationale inference",
                output_schema=output_schema,
            )
            inference = _parse_inference(
                raw,
                candidates,
                explanation_character_limit=inference_character_limit,
            )
            if cache_enabled and input_digest is not None:
                try:
                    # The provider is intentionally called without a long
                    # Context lock. Revalidate the exact direct frame in a
                    # short locked publication boundary so a late result
                    # cannot outlive deletion or replace a newer frame's
                    # useful cache slot.
                    with store._context_write_lock(ctx.name):
                        current = store.load_direct(ctx.name)
                        if current.uid != ctx.uid or context_record_digest(
                            current
                        ) != context_record_digest(ctx):
                            warnings.append(
                                "The Context changed during rationale "
                                "inference, so the result was not cached."
                            )
                        else:
                            save_rationale_inference(
                                ctx.uid,
                                target.uid,
                                input_digest,
                                _cache_record(inference),
                            )
                except (OSError, RuntimeError, ValueError):
                    warnings.append(
                        "Rationale inference was not cached because cache "
                        "storage was unavailable."
                    )
        inference_status = "AVAILABLE"
    except RationaleEvidenceTooSmall as error:
        inference_status = "INSUFFICIENT_EVIDENCE"
        inference_error = str(error)
    except (QueryProviderError, RationaleError) as error:
        # Recorded evidence remains useful when the temporary semantic
        # provider is unavailable. Unvalidated model text is never rendered.
        inference_error = str(error)
    return inference, inference_cached, inference_error, inference_status, warnings
