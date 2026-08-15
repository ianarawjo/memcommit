from __future__ import annotations

from pathlib import Path

from memcommit.commands import find_query_provider_policy as policy


def test_find_pins_terra_low_query_pins_sol_none_and_keep_timeout(monkeypatch):
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

    def connect(**kwargs):
        captured.append(kwargs)
        return _Provider()

    monkeypatch.setattr(policy, "Config", _Settings)
    monkeypatch.setattr(
        policy.CodexChatGPTProvider,
        "connect",
        staticmethod(connect),
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

    assert policy.connect_find_provider() is not None
    assert policy.connect_ordinary_query_provider() is not None

    assert captured == [
        {
            "timeout": 777.0,
            "model": "gpt-5.6-terra",
            "reasoning_effort": "low",
        },
        {
            "timeout": 777.0,
            "model": "gpt-5.6-sol",
            "reasoning_effort": "none",
        },
    ]
    assert events == [
        ("started", "find"),
        ("finished", "find", 1.0, {"provider": "codex_chatgpt"}),
        ("started", "query"),
        ("finished", "query", 1.0, {"provider": "codex_chatgpt"}),
    ]


def test_query_route_pins_codex_but_preserves_non_codex_authority(
    monkeypatch,
):
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


def test_find_and_query_commands_import_the_shared_policy_owner():
    commands = Path(__file__).parents[1] / "memcommit" / "commands"
    find_source = (commands / "find.py").read_text(encoding="utf-8")
    query_source = (commands / "query.py").read_text(encoding="utf-8")

    owner = "from memcommit.commands.find_query_provider_policy import ("
    assert owner in find_source
    assert owner in query_source
    assert "memcommit.commands.ordinary_query_provider_policy" not in query_source
