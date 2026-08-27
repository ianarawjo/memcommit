from __future__ import annotations

from pathlib import Path

from memcommit.providers import find_query as policy


def test_find_and_query_follow_the_active_profile_routes(monkeypatch):
    provider = object()
    operations: list[str] = []

    monkeypatch.setattr(
        policy,
        "_connect_active_operation",
        lambda operation: operations.append(operation) or provider,
    )

    assert policy.connect_find_provider() is provider
    assert policy.connect_ordinary_query_provider() is provider
    assert operations == ["search", "query"]


def test_query_route_pins_codex_but_preserves_non_codex_authority(
    monkeypatch,
):
    pinned = object()
    routed = object()
    calls: list[str] = []

    monkeypatch.setattr(
        policy, "_connect_pinned_codex_provider", lambda *_a, **_k: pinned
    )
    monkeypatch.setattr(
        policy,
        "_connect_configured_query_provider",
        lambda provider_id: calls.append(provider_id) or routed,
    )

    assert policy.connect_query_route_provider("codex_chatgpt") is pinned
    assert policy.connect_query_route_provider("openrouter") is routed
    assert calls == ["openrouter"]


def test_query_accepts_one_frozen_public_configuration(monkeypatch):
    captured: list[dict[str, object]] = []

    class _Identity:
        provider = "codex_chatgpt"

    class _Provider:
        identity = _Identity()

    monkeypatch.setattr(
        policy.CodexChatGPTProvider,
        "connect",
        staticmethod(lambda **kwargs: captured.append(kwargs) or _Provider()),
    )
    monkeypatch.setattr(
        policy,
        "record_provider_connection_started",
        lambda _operation: 1.0,
    )
    monkeypatch.setattr(
        policy,
        "record_provider_connection_finished",
        lambda *_args, **_kwargs: None,
    )

    policy.connect_ordinary_query_provider(
        model="gpt-5.6-sol",
        reasoning_effort="low",
        timeout_seconds=42.0,
    )

    assert captured == [
        {
            "timeout": 42.0,
            "model": "gpt-5.6-sol",
            "reasoning_effort": "low",
        }
    ]


def test_find_and_query_commands_import_the_shared_policy_owner():
    commands = (
        Path(__file__).parents[1]
        / "src"
        / "memcommit"
        / "adapters"
        / "console"
        / "commands"
    )
    find_source = (commands / "find" / "command.py").read_text(encoding="utf-8")
    query_source = (commands / "query" / "command.py").read_text(encoding="utf-8")

    owner = "from memcommit.providers.find_query import ("
    assert owner in find_source
    assert owner in query_source
    assert "memcommit.adapters.console.commands.find.provider_policy" not in find_source
    assert "memcommit.adapters.console.commands.find.provider_policy" not in query_source
    assert "memcommit.adapters.console.commands.query.provider_policy" not in query_source
