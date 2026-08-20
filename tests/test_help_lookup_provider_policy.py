"""Pinned provider policy for natural-language Help lookup."""

from __future__ import annotations

from memcommit.infrastructure.providers import find_query as policy


def test_help_lookup_pins_sol_none_and_records_help_operation(monkeypatch):
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

    assert policy.connect_help_provider() is not None

    assert captured == [
        {
            "timeout": 777.0,
            "model": "gpt-5.6-sol",
            "reasoning_effort": "none",
        }
    ]
    assert events == [
        ("started", "help"),
        ("finished", "help", 1.0, {"provider": "codex_chatgpt"}),
    ]
