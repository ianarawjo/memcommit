"""Versioned agent and MCP-facing Help discovery contract."""

from __future__ import annotations

import json

import pytest

from memcommit.api import MemCommitClient
from memcommit.interfaces.agent.help import (
    HELP_AGENT_TOOL_NAME,
    HelpAgentAdapter,
    help_agent_tool_schema,
)


def test_list_returns_all_operations_without_store_or_provider_access(tmp_path):
    root = tmp_path / "missing-store"
    adapter = HelpAgentAdapter(MemCommitClient(root=root))

    response = adapter.invoke({"version": 1, "kind": "list"})

    assert response["ok"] is True
    assert response["kind"] == "list"
    assert response["result"]["count"] == 62
    assert response["result"]["operations"][0]["name"] == "add"
    assert response["result"]["effect"] == "NONE"
    assert not root.exists()


def test_describe_returns_one_complete_stable_contract(tmp_path):
    adapter = HelpAgentAdapter(MemCommitClient(root=tmp_path / "missing-store"))

    response = adapter.invoke({"version": 1, "kind": "describe", "operation": "merge"})

    assert response["ok"] is True
    operation = response["result"]["operation"]
    assert operation == {
        "name": "merge",
        "summary": (
            "Add Source-only items to the current Target, choosing Source or "
            "Target wherever stored items conflict."
        ),
        "flow": "Source Context -> current Target Context",
        "execution": "DETERMINISTIC",
        "effect": (
            "Changes Target only after every required conflict has KEEP TARGET "
            "or TAKE SOURCE; Source stays unchanged"
        ),
        "range": "Exact roots or matching lexical descendants by complete relative path",
        "best_for": (
            "Bringing work from a copied or branched Context back into the "
            "current Context."
        ),
    }
    assert response["result"]["effect"] == "NONE"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"version": True, "kind": "list"},
        {"version": 1, "kind": "unknown"},
        {"version": 1, "kind": "list", "operation": "help"},
        {"version": 1, "kind": "describe"},
        {"version": 1, "kind": "describe", "operation": "unknown"},
    ],
)
def test_invalid_requests_fail_closed(payload, tmp_path):
    response = HelpAgentAdapter(
        MemCommitClient(root=tmp_path / "missing-store")
    ).invoke(payload)

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["retryable"] is False


def test_schema_is_json_safe_and_bounds_describe_names_to_the_catalog():
    schema = help_agent_tool_schema()

    assert schema["name"] == HELP_AGENT_TOOL_NAME
    assert schema["parameters"]["additionalProperties"] is False
    assert schema["parameters"]["allOf"][0]["else"] == {
        "not": {"required": ["operation"]}
    }
    assert len(schema["parameters"]["properties"]["operation"]["enum"]) == 62
    json.dumps(schema)
