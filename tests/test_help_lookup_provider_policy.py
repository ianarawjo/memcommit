"""Pinned provider policy for natural-language Help lookup."""

from __future__ import annotations

from memcommit.providers import find_query as policy


def test_help_lookup_follows_the_active_profile_route(monkeypatch):
    provider = object()
    operations: list[str] = []
    monkeypatch.setattr(
        policy,
        "_connect_active_operation",
        lambda operation: operations.append(operation) or provider,
    )

    assert policy.connect_help_provider() is provider
    assert operations == ["help"]
