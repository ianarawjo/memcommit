"""Versioned agent and MCP-facing Show inspection contract."""

from __future__ import annotations

import json

import pytest

import memcommit.application.ops as ops
from memcommit.adapters.python_api import MemCommitClient
from memcommit.adapters.interfaces.agent.show import (
    SHOW_AGENT_TOOL_NAME,
    ShowAgentAdapter,
    show_agent_tool_schema,
)
from memcommit.store import MemoryStore


def _client(root):
    store = MemoryStore(root=root)
    context = ops.init("agent/context")
    memory = ops.add(context, "visible agent content")
    query = ops.reference_query_context(
        "agent/concealed",
        "concealed-source-uid",
        context,
    )
    store.save(context)
    store.set_current(context.name)
    return MemCommitClient(root=root), memory, query


def test_context_and_memory_results_are_typed_and_read_only(tmp_path):
    client, memory, _query = _client(tmp_path / "store")
    adapter = ShowAgentAdapter(client)

    context = adapter.invoke({"version": 1, "kind": "inspect"})
    selected = adapter.invoke(
        {
            "version": 1,
            "kind": "inspect",
            "context_name": "agent/context",
            "selector": memory.uid[:8],
        }
    )

    assert context["ok"] is True
    assert context["result"]["kind"] == "context"
    assert context["result"]["effect"] == "NONE"
    assert selected["result"]["kind"] == "memory"
    assert selected["result"]["content"] == "visible agent content"
    assert selected["result"]["source"] == {
        "access": "OWNED",
        "reach": "DIRECT",
        "form": "MEMORY",
        "states": [],
        "permissions": [],
    }


def test_query_view_never_contains_concealed_content(tmp_path):
    client, _memory, query = _client(tmp_path / "store")

    response = ShowAgentAdapter(client).invoke(
        {"version": 1, "kind": "inspect", "selector": query.uid[:8]}
    )

    assert response["ok"] is True
    assert response["result"]["kind"] == "query_view"
    assert response["result"]["name"] == "agent/concealed"
    assert "content" not in response["result"]
    assert "concealed-source-uid" not in json.dumps(response)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"version": True, "kind": "inspect"},
        {"version": 1, "kind": "unknown"},
        {"version": 1, "kind": "inspect", "selector": ""},
        {"version": 1, "kind": "inspect", "extra": True},
    ],
)
def test_invalid_requests_fail_closed(payload, tmp_path):
    client, _memory, _query = _client(tmp_path / "store")

    response = ShowAgentAdapter(client).invoke(payload)

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["retryable"] is False


def test_unavailable_context_has_stable_error_category(tmp_path):
    client, _memory, _query = _client(tmp_path / "store")

    response = ShowAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "inspect",
            "context_name": "missing",
        }
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "context_unavailable"


def test_schema_is_json_safe_and_allows_exact_optional_targeting():
    schema = show_agent_tool_schema()

    assert schema["name"] == SHOW_AGENT_TOOL_NAME
    assert schema["parameters"]["additionalProperties"] is False
    assert schema["parameters"]["required"] == ["version", "kind"]
    assert set(schema["parameters"]["properties"]) == {
        "version",
        "kind",
        "context_name",
        "selector",
    }
    json.dumps(schema)
