from __future__ import annotations

from memcommit.study_prewarm.quality import (
    PrewarmQualityRelation,
    compare_prewarm_quality,
    highest_quality_candidates,
    prewarm_quality_satisfies,
)


def _identity(
    model: str = "gpt-5.6-sol",
    reasoning: str | None = "medium",
    provider: str = "codex_chatgpt",
):
    return provider, model, reasoning


def test_higher_reasoning_cache_satisfies_lower_configured_request():
    cached = _identity(reasoning="medium")
    requested = _identity(reasoning="none")

    assert (
        compare_prewarm_quality(cached, requested)
        == PrewarmQualityRelation.CACHE_DOMINATES
    )
    assert prewarm_quality_satisfies(cached, requested)
    assert not prewarm_quality_satisfies(requested, cached)


def test_both_model_and_reasoning_must_be_at_least_requested_quality():
    assert prewarm_quality_satisfies(
        _identity(model="gpt-5.6-sol", reasoning="medium"),
        _identity(model="gpt-5.6-terra", reasoning="low"),
    )
    assert (
        compare_prewarm_quality(
            _identity(model="gpt-5.6-sol", reasoning="low"),
            _identity(model="gpt-5.6-terra", reasoning="medium"),
        )
        == PrewarmQualityRelation.INCOMPARABLE
    )


def test_provider_unknown_model_and_default_reasoning_do_not_infer_quality():
    assert not prewarm_quality_satisfies(
        _identity(provider="openrouter"),
        _identity(provider="codex_chatgpt"),
    )
    assert not prewarm_quality_satisfies(
        _identity(model="future-model", reasoning="high"),
        _identity(model="gpt-5.6-sol", reasoning="none"),
    )
    assert not prewarm_quality_satisfies(
        _identity(reasoning="medium"),
        _identity(reasoning=None),
    )
    assert not prewarm_quality_satisfies(
        _identity(model="gpt-5.6-sol", reasoning=None),
        _identity(model="gpt-5.6-terra", reasoning=None),
    )
    assert prewarm_quality_satisfies(
        _identity(model="future-model", reasoning="medium"),
        _identity(model="future-model", reasoning="medium"),
    )


def test_unique_higher_candidate_displaces_lower_but_ambiguity_is_retained():
    low = _identity(reasoning="low")
    medium = _identity(reasoning="medium")
    assert highest_quality_candidates([(low, "low"), (medium, "medium")]) == ("medium",)
    assert highest_quality_candidates([(medium, "a"), (medium, "b")]) == (
        "a",
        "b",
    )
