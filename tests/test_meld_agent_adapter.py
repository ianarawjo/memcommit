"""Versioned agent-tool coverage for the public Meld facade."""

from __future__ import annotations

import pytest

from memcommit.api import MeldProviderFailure, MeldSessionResult, MemCommitClient
from memcommit.interfaces.agent.meld import (
    MELD_AGENT_TOOL_NAME,
    MeldAgentAdapter,
    meld_agent_tool_schema,
)


@pytest.fixture
def client(tmp_path):
    return MemCommitClient(root=tmp_path / "store", create=True)


def _session():
    return MeldSessionResult(
        session_uid="session-1",
        version="saved-version",
        mode="DIRECTIONAL",
        state="AWAITING_REPLY",
        left_context="incoming",
        right_context="baseline",
        target_context="baseline",
        turn_count=1,
        overview="Reviewed.",
        ready_to_apply=False,
        issues=(),
        proposals=(),
        origin="PROVIDER",
    )


def test_start_action_calls_public_facade_and_returns_json(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        client,
        "start_meld",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or _session()),
    )

    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "start",
            "left_context": "incoming",
            "right_context": "baseline",
        }
    )

    assert result["ok"] is True
    assert result["result"]["session"]["session_uid"] == "session-1"
    assert calls[0][0] == ()
    assert calls[0][1]["mode"] == "directional"


def test_restart_action_requires_and_forwards_the_saved_version(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        client,
        "restart_meld",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or _session()),
    )

    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "restart",
            "left_context": "incoming",
            "right_context": "baseline",
            "target_context": "baseline",
            "expected_version": "saved-version",
        }
    )

    assert result["ok"] is True
    assert result["result"]["session"]["version"] == "saved-version"
    assert calls[0][1]["expected_version"] == "saved-version"


def test_action_rejects_fields_owned_by_another_kind(client):
    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "open",
            "target_context": "baseline",
            "comment": "not valid here",
        }
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"


def test_provider_failure_is_bounded_and_retryable(client, monkeypatch):
    def fail(**kwargs):
        raise MeldProviderFailure("private endpoint detail")

    monkeypatch.setattr(client, "comment_meld", fail)
    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "comment",
            "target_context": "baseline",
            "comment": "Use the first reading.",
        }
    )

    assert result["ok"] is False
    assert result["error"] == {
        "code": "provider_failure",
        "message": "The Meld provider failed.",
        "retryable": True,
    }


def test_exact_issue_option_forwards_the_reviewed_version(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        client,
        "comment_meld",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or _session()),
    )

    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "comment",
            "target_context": "baseline",
            "issue_uid": "issue-1",
            "option_uid": "option-1",
            "expected_version": "saved-version",
        }
    )

    assert result["ok"] is True
    assert calls == [
        (
            (),
            {
                "target_context": "baseline",
                "comment": "",
                "issue_uid": "issue-1",
                "option_uid": "option-1",
                "expected_version": "saved-version",
                "revision": "EXTEND",
                "revises_turn_uids": (),
            },
        )
    ]


def test_exact_issue_option_requires_the_reviewed_version(client):
    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "comment",
            "target_context": "baseline",
            "issue_uid": "issue-1",
            "option_uid": "option-1",
        }
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"
    assert "expected_version" in result["error"]["message"]


def test_schema_is_fresh_and_uses_stable_tool_name():
    first = meld_agent_tool_schema()
    first["name"] = "changed"

    assert meld_agent_tool_schema()["name"] == MELD_AGENT_TOOL_NAME
    assert "option_uid" in meld_agent_tool_schema()["parameters"]["properties"]
