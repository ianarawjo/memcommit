"""Agent and MCP projections over public Distill and Elaborate calls."""

from __future__ import annotations

import json

import memcommit.ops as ops
from memcommit.api import MemCommitClient
from memcommit.distill import DISTILL_PAYLOAD_MARKER
from memcommit.elaborate import ELABORATE_PAYLOAD_MARKER
from memcommit.fit_judgment import FIT_JUDGMENT_PAYLOAD_MARKER
from memcommit.interfaces.agent import (
    DISTILL_AGENT_TOOL_NAME,
    ELABORATE_AGENT_CONTRACT_VERSION,
    ELABORATE_AGENT_TOOL_NAME,
    FIT_AGENT_TOOL_NAME,
    build_default_agent_tool_registry,
)
from memcommit.interfaces.mcp import McpRegistryProjection
from memcommit.store import MemoryStore


class AgentSemanticProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "fit_propositions":
            payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
            question = payload["questions"][0]
            aliases = [
                item["proposition_id"]
                for item in (*question["background"], *question["propositions"])
            ]
            return json.dumps(
                {
                    "overview": "The complete set is compatible.",
                    "judgments": [
                        {
                            "question_id": "fit",
                            "verdict": "YES",
                            "reason": "The Goal and Rule can coexist.",
                            "considered_proposition_ids": aliases,
                            "material_proposition_ids": [],
                            "consistent_reading": "",
                            "inconsistent_reading": "",
                        }
                    ],
                }
            )
        if operation == "distill_context":
            payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
            aliases = [item["memory_id"] for item in payload["source"]["memories"]]
            return json.dumps(
                {
                    "overview": "One Rule is supported.",
                    "rules": [
                        {
                            "content": "Confirm before acting.",
                            "rationale": "The proposition supports it.",
                            "support_memory_ids": aliases,
                            "boundary_memory_ids": [],
                        }
                    ],
                    "outside_memory_ids": [],
                }
            )
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        assert payload["mode"] == "GOAL_TO_RULES"
        number = payload["number"]
        return json.dumps(
            {
                "overview": f"{number} suggested Rules.",
                "rules": [
                    {
                        "content": f"Confirm option {index} before acting.",
                        "rationale": f"This makes Goal branch {index} operational.",
                    }
                    for index in range(1, number + 1)
                ],
            }
        )


def test_default_registry_and_mcp_expose_read_only_semantic_tools(isolated_store):
    store = MemoryStore()
    context = ops.init("agent/semantic")
    ops.add(context, "The person confirmed before the action.")
    store.save(context)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=AgentSemanticProvider,
    )
    registry = build_default_agent_tool_registry(client)

    distill = registry.invoke(
        DISTILL_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "context",
            "context_name": context.name,
        },
    )
    elaborate = registry.invoke(
        ELABORATE_AGENT_TOOL_NAME,
        {
            "version": 3,
            "kind": "goal_to_rules",
            "goal": "Confirm before acting.",
            "number": 1,
        },
    )
    fit = registry.invoke(
        FIT_AGENT_TOOL_NAME,
        {
            "version": 1,
            "propositions": [
                {"alias": "goal", "role": "GOAL", "content": "Keep access."},
                {"alias": "rule", "role": "RULE", "content": "Use the staff entrance."},
            ],
        },
    )
    mcp_names = tuple(tool.name for tool in McpRegistryProjection(registry).list_tools())

    assert distill["ok"] is True
    assert distill["result"]["effect"] == "NONE"
    assert elaborate["ok"] is True
    assert elaborate["result"]["verification"] == "UNVERIFIED"
    assert len(elaborate["result"]["rules"]) == 1
    assert fit["ok"] is True
    assert fit["result"]["verdict"] == "YES"
    assert fit["result"]["effect"] == "NONE"
    assert DISTILL_AGENT_TOOL_NAME in mcp_names
    assert ELABORATE_AGENT_TOOL_NAME in mcp_names
    assert FIT_AGENT_TOOL_NAME in mcp_names
    assert not store.context_exists("agent/rules")


def test_semantic_agent_elaborate_accepts_an_exact_number(isolated_store):
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=AgentSemanticProvider,
    )
    registry = build_default_agent_tool_registry(client)

    result = registry.invoke(
        ELABORATE_AGENT_TOOL_NAME,
        {
            "version": ELABORATE_AGENT_CONTRACT_VERSION,
            "kind": "goal_to_rules",
            "goal": "Confirm before acting.",
            "number": 5,
        },
    )

    assert result["ok"] is True
    assert len(result["result"]["rules"]) == 5
    schema = next(
        item
        for item in registry.tool_schemas()
        if item["name"] == ELABORATE_AGENT_TOOL_NAME
    )
    assert all(
        "maximum" not in branch["properties"]["number"]
        for branch in schema["parameters"]["oneOf"]
    )


def test_semantic_agent_rejects_unknown_fields_before_provider(tmp_path):
    root = tmp_path / "store"
    registry = build_default_agent_tool_registry(MemCommitClient(root=root))

    result = registry.invoke(
        ELABORATE_AGENT_TOOL_NAME,
        {
            "version": 3,
            "kind": "goal_to_rules",
            "goal": "A Goal",
            "save": True,
        },
    )

    assert result["error"]["code"] == "invalid_request"
    assert not root.exists()


def test_semantic_agent_ground_routes_preserve_context_error_category(
    isolated_store,
):
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=AgentSemanticProvider,
    )
    registry = build_default_agent_tool_registry(client)

    distill = registry.invoke(
        DISTILL_AGENT_TOOL_NAME,
        {"version": 1, "kind": "ground", "ground_name": "missing-ground"},
    )
    elaborate = registry.invoke(
        ELABORATE_AGENT_TOOL_NAME,
        {
            "version": 3,
            "kind": "ground_goal_to_rules",
            "ground_name": "missing-ground",
        },
    )

    assert distill["error"]["code"] == "context_unavailable"
    assert elaborate["error"]["code"] == "context_unavailable"
