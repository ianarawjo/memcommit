"""Versioned agent-facing semantic Search contract."""

from __future__ import annotations

import json

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import MemCommitClient
from memcommit.adapters.agent.search import (
    SEARCH_AGENT_TOOL_NAME,
    SearchAgentAdapter,
    search_agent_tool_schema,
)
from memcommit.persistence.store import MemoryStore


class _Provider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "search"
        payload = json.loads(prompt.split("SEARCH PAYLOAD:\n", 1)[1])
        candidate = payload["candidates"][0]
        return json.dumps(
            {
                "matches": [{"candidate_id": candidate["candidate_id"]}],
                "related_query": "",
                "related_matches": [],
            }
        )


def _adapter(root):
    store = MemoryStore(root=root)
    context = ops.init("agent/search")
    ops.add(context, "Agent-visible semantic content.")
    store.save(context)
    store.set_current(context.name)
    return SearchAgentAdapter(
        MemCommitClient(
            root=root,
            semantic_provider_factory=_Provider,
        )
    )


def test_agent_search_returns_bounded_read_only_result(tmp_path):
    response = _adapter(tmp_path / "store").invoke(
        {"version": 1, "kind": "search", "query": "semantic content"}
    )

    assert response["ok"] is True
    assert response["result"]["effect"] == "NONE"
    assert response["result"]["items"][0]["content"] == (
        "Agent-visible semantic content."
    )


def test_agent_search_rejects_unknown_fields_without_provider(tmp_path):
    response = _adapter(tmp_path / "store").invoke(
        {
            "version": 1,
            "kind": "search",
            "query": "content",
            "unexpected": True,
        }
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"


def test_search_tool_schema_is_exact_and_json_safe():
    schema = search_agent_tool_schema()

    assert schema["name"] == SEARCH_AGENT_TOOL_NAME
    assert schema["parameters"]["additionalProperties"] is False
    assert schema["parameters"]["required"] == ["version", "kind", "query"]
    json.dumps(schema)
