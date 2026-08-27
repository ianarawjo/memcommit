"""Conservative quality compatibility for declared Study prewarms.

Artifact identity remains exact provenance.  This module answers the separate
question of whether that recorded identity is at least as capable as the
configuration requested for a new run.
"""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from memcommit.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
)


SemanticIdentity = tuple[str, str | None, str | None]
_T = TypeVar("_T")

# This is a deliberately closed, reviewed ordering.  Unknown models are only
# comparable to themselves so a newly named model cannot silently inherit a
# quality claim from naming convention or release recency.
_CODEX_MODEL_QUALITY = {
    "gpt-5.6-luna": 0,
    "gpt-5.6-terra": 1,
    "gpt-5.6-sol": 2,
}
_CODEX_REASONING_QUALITY = {
    effort: rank for rank, effort in enumerate(CODEX_REASONING_EFFORTS)
}


class PrewarmQualityRelation(str, Enum):
    """Partial-order relation of a cached identity to a requested identity."""

    EQUIVALENT = "EQUIVALENT"
    CACHE_DOMINATES = "CACHE_DOMINATES"
    CACHE_LOWER = "CACHE_LOWER"
    INCOMPARABLE = "INCOMPARABLE"

    @property
    def satisfies_request(self) -> bool:
        return self in {self.EQUIVALENT, self.CACHE_DOMINATES}


def _rank_relation(
    cached: str | None,
    requested: str | None,
    ranks: dict[str, int],
) -> int | None:
    if cached == requested:
        return 0
    # ``None`` can mean provider-selected/default behavior.  Its capability is
    # not inferred in either direction.
    if cached is None or requested is None:
        return None
    cached_rank = ranks.get(cached)
    requested_rank = ranks.get(requested)
    if cached_rank is None or requested_rank is None:
        return None
    return (cached_rank > requested_rank) - (cached_rank < requested_rank)


def compare_prewarm_quality(
    cached: SemanticIdentity,
    requested: SemanticIdentity,
) -> PrewarmQualityRelation:
    """Compare exact provenance identities through a conservative partial order."""

    if cached == requested:
        return PrewarmQualityRelation.EQUIVALENT
    cached_provider, cached_model, cached_reasoning = cached
    requested_provider, requested_model, requested_reasoning = requested
    if (
        cached_provider != requested_provider
        or cached_provider != CODEX_CHATGPT_PROVIDER
    ):
        return PrewarmQualityRelation.INCOMPARABLE
    if any(
        value is None
        for value in (
            cached_model,
            cached_reasoning,
            requested_model,
            requested_reasoning,
        )
    ):
        # A provider-selected default can change independently of this cache
        # contract, so only the full-tuple equality handled above is safe.
        return PrewarmQualityRelation.INCOMPARABLE
    model_relation = _rank_relation(
        cached_model,
        requested_model,
        _CODEX_MODEL_QUALITY,
    )
    reasoning_relation = _rank_relation(
        cached_reasoning,
        requested_reasoning,
        _CODEX_REASONING_QUALITY,
    )
    if model_relation is None or reasoning_relation is None:
        return PrewarmQualityRelation.INCOMPARABLE
    if model_relation >= 0 and reasoning_relation >= 0:
        return PrewarmQualityRelation.CACHE_DOMINATES
    if model_relation <= 0 and reasoning_relation <= 0:
        return PrewarmQualityRelation.CACHE_LOWER
    return PrewarmQualityRelation.INCOMPARABLE


def prewarm_quality_satisfies(
    cached: SemanticIdentity,
    requested: SemanticIdentity,
) -> bool:
    """Return whether one cached artifact may satisfy the configured request."""

    return compare_prewarm_quality(cached, requested).satisfies_request


def highest_quality_candidates(
    candidates: list[tuple[SemanticIdentity, _T]],
) -> tuple[_T, ...]:
    """Return undominated compatible candidates without resolving ambiguity.

    A unique strictly better artifact replaces a lower compatible artifact.
    Equal-quality duplicates and cross-axis maxima remain visible to the
    operation, which can retain its existing fail-closed ambiguity behavior.
    """

    maxima: list[_T] = []
    for index, (identity, candidate) in enumerate(candidates):
        if any(
            compare_prewarm_quality(other_identity, identity)
            == PrewarmQualityRelation.CACHE_DOMINATES
            for other_index, (other_identity, _other) in enumerate(candidates)
            if other_index != index
        ):
            continue
        maxima.append(candidate)
    return tuple(maxima)


def compatible_cached_identities(
    requested: SemanticIdentity,
) -> tuple[SemanticIdentity, ...]:
    """Enumerate the closed identity set useful for content-addressed lookup."""

    provider, model, reasoning = requested
    if provider != CODEX_CHATGPT_PROVIDER:
        return (requested,)
    model_rank = _CODEX_MODEL_QUALITY.get(model) if model is not None else None
    reasoning_rank = (
        _CODEX_REASONING_QUALITY.get(reasoning) if reasoning is not None else None
    )
    if model_rank is None or reasoning_rank is None:
        return (requested,)
    return tuple(
        (provider, cached_model, cached_reasoning)
        for cached_model, cached_model_rank in _CODEX_MODEL_QUALITY.items()
        for cached_reasoning, cached_reasoning_rank in _CODEX_REASONING_QUALITY.items()
        if cached_model_rank >= model_rank and cached_reasoning_rank >= reasoning_rank
    )
