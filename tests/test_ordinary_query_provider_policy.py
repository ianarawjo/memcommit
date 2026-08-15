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


def test_ordinary_query_pins_sol_none_and_keeps_shared_timeout(monkeypatch):
    captured: list[dict[str, object]] = []
    events: list[tuple[object, ...]] = []

    class _Settings:
        @staticmethod
        def semantic_timeout_seconds():
            return 777.0

    class _Identity:
        provider = "codex_chatgpt"

    class _Provider:
        identity = _Identity()

    monkeypatch.setattr(policy, "Config", _Settings)
    monkeypatch.setattr(
        policy.CodexChatGPTProvider,
        "connect",
        staticmethod(lambda **kwargs: captured.append(kwargs) or _Provider()),
    )
    monkeypatch.setattr(
        policy,
        "record_provider_connection_started",
        lambda operation: events.append(("started", operation)) or 1.0,
    )
    monkeypatch.setattr(
        policy,
        "record_provider_connection_finished",
        lambda operation, started_at, **kwargs: events.append(
            ("finished", operation, started_at, kwargs)
        ),
    )

    assert policy.connect_ordinary_query_provider() is not None
    assert captured == [
        {
            "timeout": 777.0,
            "model": "gpt-5.6-sol",
            "reasoning_effort": "none",
        }
    ]
    assert events == [
        ("started", "query"),
        ("finished", "query", 1.0, {"provider": "codex_chatgpt"}),
    ]


def test_query_route_pins_codex_but_preserves_non_codex_authority(monkeypatch):
    pinned = object()
    routed = object()
    calls: list[str] = []

    monkeypatch.setattr(
        policy,
        "connect_ordinary_query_provider",
        lambda: pinned,
    )
    monkeypatch.setattr(
        policy,
        "_connect_configured_query_provider",
        lambda provider_id: calls.append(provider_id) or routed,
    )

    assert policy.connect_query_route_provider("codex_chatgpt") is pinned
    assert policy.connect_query_route_provider("openrouter") is routed
    assert calls == ["openrouter"]
