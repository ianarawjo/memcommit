"""Pinned provider boundary for one-shot ordinary Query."""

from __future__ import annotations

from memcommit.commands import ordinary_query_provider_policy as compatibility
from memcommit.infrastructure.providers import find_query as policy
from memcommit.infrastructure.providers.find_query import QUERY_PROVIDER_POLICY


def test_ordinary_query_compatibility_constants_follow_shared_policy():
    assert compatibility.ORDINARY_QUERY_MODEL == QUERY_PROVIDER_POLICY.model
    assert (
        compatibility.ORDINARY_QUERY_REASONING_EFFORT
        == QUERY_PROVIDER_POLICY.reasoning_effort
    )
    assert (
        compatibility.connect_ordinary_query_provider
        is policy.connect_ordinary_query_provider
    )
    assert (
        compatibility.connect_query_route_provider
        is policy.connect_query_route_provider
    )


def test_ordinary_query_follows_the_active_profile_route(monkeypatch):
    provider = object()
    operations: list[str] = []
    monkeypatch.setattr(
        policy,
        "_connect_active_operation",
        lambda operation: operations.append(operation) or provider,
    )

    assert policy.connect_ordinary_query_provider() is provider
    assert operations == ["query"]


def test_query_route_pins_codex_but_preserves_non_codex_authority(monkeypatch):
    pinned = object()
    routed = object()
    calls: list[str] = []

    monkeypatch.setattr(policy, "_connect_pinned_codex_provider", lambda *_a, **_k: pinned)
    monkeypatch.setattr(
        policy,
        "_connect_configured_query_provider",
        lambda provider_id: calls.append(provider_id) or routed,
    )

    assert policy.connect_query_route_provider("codex_chatgpt") is pinned
    assert policy.connect_query_route_provider("openrouter") is routed
    assert calls == ["openrouter"]
