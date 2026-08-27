"""Versioned agent contracts for public Compare."""

from __future__ import annotations

import pytest

from memcommit.adapters.python_api import (
    CompareConflictError,
    ComparisonFrameResult,
    ComparisonResult,
    MemCommitClient,
)
from memcommit.interfaces.agent.compare import (
    COMPARE_AGENT_TOOL_NAME,
    CompareAgentAdapter,
    compare_agent_tool_schema,
)


@pytest.fixture
def client(tmp_path):
    return MemCommitClient(root=tmp_path / "store")


def _result(*, origin="LIVE"):
    return ComparisonResult(
        analysis_uid="analysis-1",
        version="a" * 64,
        ruleset_version="peer-relations-v3",
        frames=(
            ComparisonFrameResult(
                "frame-a", "REFERENCE", "a", ("memory-a",), None
            ),
            ComparisonFrameResult(
                "frame-b", "COMPARED", "b", ("memory-b",), None
            ),
        ),
        include_descendants=(False, True),
        overview="The peers overlap and differ in one bounded way.",
        reports=None,
        relations=(),
        issues=(),
        origin=origin,
        durable=True,
        retention=None,
    )


def test_run_forwards_the_complete_ordered_scope(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        client,
        "compare_contexts",
        lambda **kwargs: (calls.append(kwargs) or _result()),
    )

    response = CompareAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "run",
            "reference_context": "a",
            "compared_context": "b",
            "reference_descendants": False,
            "compared_descendants": True,
            "reference_memory": None,
            "compared_memory": None,
        }
    )

    assert response["ok"] is True
    assert response["result"]["effect"] == "COMPARE_ANALYSIS_SLOT"
    assert calls == [
        {
            "reference_context": "a",
            "compared_context": "b",
            "reference_descendants": False,
            "compared_descendants": True,
            "reference_memory": None,
            "compared_memory": None,
        }
    ]


def test_open_and_refresh_use_the_exact_saved_identity(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        client,
        "open_comparison",
        lambda **kwargs: (calls.append(("open", kwargs)) or _result(origin="SAVED_OPEN")),
    )
    monkeypatch.setattr(
        client,
        "refresh_comparison",
        lambda **kwargs: (calls.append(("refresh", kwargs)) or _result()),
    )
    adapter = CompareAgentAdapter(client)

    opened = adapter.invoke(
        {"version": 1, "kind": "open", "analysis_uid": "analysis-1"}
    )
    refreshed = adapter.invoke(
        {
            "version": 1,
            "kind": "refresh",
            "analysis_uid": "analysis-1",
            "expected_version": "a" * 64,
        }
    )

    assert opened["result"]["effect"] == "NONE"
    assert refreshed["ok"] is True
    assert calls == [
        ("open", {"analysis_uid": "analysis-1"}),
        (
            "refresh",
            {"analysis_uid": "analysis-1", "expected_version": "a" * 64},
        ),
    ]


def test_refresh_requires_the_reviewed_version_before_dispatch(client, monkeypatch):
    monkeypatch.setattr(
        client,
        "refresh_comparison",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("invalid refresh reached the client")
        ),
    )

    response = CompareAgentAdapter(client).invoke(
        {"version": 1, "kind": "refresh", "analysis_uid": "analysis-1"}
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"
    assert "expected_version" in response["error"]["message"]


def test_stale_refresh_is_a_bounded_nonretryable_conflict(client, monkeypatch):
    monkeypatch.setattr(
        client,
        "refresh_comparison",
        lambda **kwargs: (_ for _ in ()).throw(CompareConflictError("stale")),
    )

    response = CompareAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "refresh",
            "analysis_uid": "analysis-1",
            "expected_version": "a" * 64,
        }
    )

    assert response["error"] == {
        "code": "concurrent_update",
        "message": "The Compare changed concurrently.",
        "retryable": False,
    }


def test_schema_is_fresh_and_describes_read_only_context_behavior():
    first = compare_agent_tool_schema()
    first["name"] = "changed"
    current = compare_agent_tool_schema()

    assert current["name"] == COMPARE_AGENT_TOOL_NAME
    assert "read-only" in current["description"]
    assert "required only for refresh" in current["parameters"]["properties"][
        "expected_version"
    ]["description"]
