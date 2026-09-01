"""Versioned agent-tool coverage for the public Meld facade."""

from __future__ import annotations

import pytest

from memcommit.adapters.python_api import (
    MeldDecisionInput,
    MeldProviderFailure,
    MeldSessionResult,
    MemCommitClient,
)
from memcommit.adapters.agent.meld import (
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

    monkeypatch.setattr(client, "resolve_meld", fail)
    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "resolve",
            "target_context": "baseline",
            "expected_version": "saved-version",
            "decisions": [],
        }
    )

    assert result["ok"] is False
    assert result["error"] == {
        "code": "provider_failure",
        "message": "The Meld provider failed.",
        "retryable": True,
    }


def test_complete_decision_set_forwards_the_reviewed_version(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        client,
        "resolve_meld",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or _session()),
    )

    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "resolve",
            "target_context": "baseline",
            "expected_version": "saved-version",
            "decisions": [
                {"issue_uid": "issue-1", "kind": "confirm"},
                {
                    "issue_uid": "issue-2",
                    "kind": "intent",
                    "intent": "Keep named greetings as exceptions.",
                },
                {"issue_uid": "issue-3", "kind": "force"},
            ],
        }
    )

    assert result["ok"] is True
    assert calls == [
        (
            (),
            {
                "target_context": "baseline",
                "expected_version": "saved-version",
                "decisions": (
                    MeldDecisionInput("issue-1", "confirm"),
                    MeldDecisionInput(
                        "issue-2",
                        "intent",
                        "Keep named greetings as exceptions.",
                    ),
                    MeldDecisionInput("issue-3", "force"),
                ),
            },
        )
    ]


def test_resolve_requires_the_reviewed_version(client):
    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "resolve",
            "target_context": "baseline",
            "decisions": [],
        }
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"
    assert "expected_version" in result["error"]["message"]


def test_intent_decision_requires_nonblank_intent(client):
    result = MeldAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "resolve",
            "target_context": "baseline",
            "expected_version": "saved-version",
            "decisions": [{"issue_uid": "issue-1", "kind": "intent"}],
        }
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"
    assert "nonblank intent" in result["error"]["message"]


@pytest.mark.parametrize("kind", ("comment", "preserve", "defer", "apply"))
def test_retired_meld_agent_actions_are_not_executable(client, kind):
    result = MeldAgentAdapter(client).invoke({"version": 1, "kind": kind})

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"
    assert "resolve" in result["error"]["message"]


def test_schema_is_fresh_and_uses_stable_tool_name():
    first = meld_agent_tool_schema()
    first["name"] = "changed"

    assert meld_agent_tool_schema()["name"] == MELD_AGENT_TOOL_NAME
    properties = meld_agent_tool_schema()["parameters"]["properties"]
    assert "decisions" in properties
    assert properties["kind"]["enum"] == ["start", "restart", "open", "resolve"]
    assert "required by restart" in properties["expected_version"]["description"]
