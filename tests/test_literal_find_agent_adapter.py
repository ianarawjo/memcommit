"""Versioned agent contract for deterministic Find."""

from __future__ import annotations

import json

import memcommit.application.ops as ops
from memcommit.adapters.python_api import MemCommitClient
from memcommit.interfaces.agent.find import (
    FIND_AGENT_TOOL_NAME,
    FindAgentAdapter,
    find_agent_tool_schema,
)
from memcommit.store import MemoryStore


def _adapter(root):
    store = MemoryStore(root=root)
    context = ops.init("agent/find")
    ops.add(context, "literal needle and literal needle")
    store.save(context)
    store.set_current(context.name)

    def provider():
        raise AssertionError("Agent Find must not connect a provider.")

    return FindAgentAdapter(
        MemCommitClient(root=root, semantic_provider_factory=provider)
    )


def test_agent_find_returns_every_span_and_explicit_provider_receipt(tmp_path):
    response = _adapter(tmp_path / "store").invoke(
        {"version": 1, "kind": "find", "pattern": "needle"}
    )

    assert response["ok"] is True
    assert response["result"]["effect"] == "NONE"
    assert response["result"]["provider_used"] is False
    assert response["result"]["occurrence_count"] == 2


def test_agent_find_fails_closed_on_unknown_fields(tmp_path):
    response = _adapter(tmp_path / "store").invoke(
        {
            "version": 1,
            "kind": "find",
            "pattern": "needle",
            "semantic": True,
        }
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"


def test_find_tool_schema_is_exact_and_json_safe():
    schema = find_agent_tool_schema()

    assert schema["name"] == FIND_AGENT_TOOL_NAME
    assert schema["parameters"]["required"] == ["version", "kind", "pattern"]
    assert schema["parameters"]["additionalProperties"] is False
    json.dumps(schema)
