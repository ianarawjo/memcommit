"""Agent registry coverage over public Distill and Makemore calls."""

from __future__ import annotations

import json

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import MemCommitClient
from memcommit.application.operations.distill.model import DISTILL_PAYLOAD_MARKER
from memcommit.application.operations.makemore.model import MAKEMORE_PAYLOAD_MARKER
from memcommit.application.operations.fit.judgment import FIT_JUDGMENT_PAYLOAD_MARKER
from memcommit.adapters.agent.distill import DISTILL_AGENT_TOOL_NAME
from memcommit.adapters.agent.makemore import (
    MAKEMORE_AGENT_CONTRACT_VERSION,
    MAKEMORE_AGENT_TOOL_NAME,
)
from memcommit.adapters.agent.fit import FIT_AGENT_TOOL_NAME
from memcommit.adapters.agent.registry import build_default_agent_tool_registry
from memcommit.persistence.store import MemoryStore
from tests.distill_goal_fit_support import passing_distill_goal_fit_response
from tests.makemore_validation_support import (
    passing_makemore_validation_response,
)


class AgentSemanticProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_makemore_validation_response(prompt, operation)
        if validation is not None:
            return validation
        validation = passing_distill_goal_fit_response(prompt, operation)
        if validation is not None:
            return validation
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
        payload = json.loads(prompt.split(MAKEMORE_PAYLOAD_MARKER, 1)[1])
        number = payload["number"]
        if payload["mode"] == "RULES_TO_CASES":
            return json.dumps(
                {
                    "overview": f"{number} suggested Cases.",
                    "cases": [
                        {
                            "proposition": (
                                f"The person confirms option {index} before acting."
                            ),
                            "expected": f"Proceed with option {index}.",
                            "rationale": "This Case follows the complete Rule set.",
                            "case_role": "FIT",
                            "rule_checks": [
                                {
                                    "source_rule_index": rule_index,
                                    "evidence": "The Case visibly follows this Rule.",
                                }
                                for rule_index, _rule in enumerate(
                                    payload["inputs"], 1
                                )
                            ],
                        }
                        for index in range(1, number + 1)
                    ],
                }
            )
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


def test_default_registry_exposes_read_only_semantic_tools(isolated_store):
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
    makemore = registry.invoke(
        MAKEMORE_AGENT_TOOL_NAME,
        {
            "version": MAKEMORE_AGENT_CONTRACT_VERSION,
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
    tool_names = registry.tool_names

    assert distill["ok"] is True
    assert distill["result"]["effect"] == "NONE"
    assert makemore["ok"] is True
    assert makemore["result"]["verification"] == "UNVERIFIED"
    assert len(makemore["result"]["rules"]) == 1
    assert fit["ok"] is True
    assert fit["result"]["verdict"] == "YES"
    assert fit["result"]["effect"] == "NONE"
    assert DISTILL_AGENT_TOOL_NAME in tool_names
    assert MAKEMORE_AGENT_TOOL_NAME in tool_names
    assert FIT_AGENT_TOOL_NAME in tool_names
    assert not store.context_exists("agent/rules")


def test_semantic_agent_makemore_accepts_an_exact_number(isolated_store):
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=AgentSemanticProvider,
    )
    registry = build_default_agent_tool_registry(client)

    result = registry.invoke(
        MAKEMORE_AGENT_TOOL_NAME,
        {
            "version": MAKEMORE_AGENT_CONTRACT_VERSION,
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
        if item["name"] == MAKEMORE_AGENT_TOOL_NAME
    )
    assert all(
        "maximum" not in branch["properties"]["number"]
        for branch in schema["parameters"]["oneOf"]
    )


def test_semantic_agent_makemore_exposes_case_validation(isolated_store):
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=AgentSemanticProvider,
    )
    registry = build_default_agent_tool_registry(client)

    best_effort = registry.invoke(
        MAKEMORE_AGENT_TOOL_NAME,
        {
            "version": MAKEMORE_AGENT_CONTRACT_VERSION,
            "kind": "rules_to_cases",
            "rules": ["Act only after explicit confirmation."],
            "number": 1,
        },
    )
    result = registry.invoke(
        MAKEMORE_AGENT_TOOL_NAME,
        {
            "version": MAKEMORE_AGENT_CONTRACT_VERSION,
            "kind": "rules_to_cases",
            "rules": ["Act only after explicit confirmation."],
            "number": 1,
            "strict": True,
        },
    )

    assert best_effort["ok"] is True
    assert best_effort["result"]["quality_policy"] == "BEST_EFFORT"
    assert best_effort["result"]["cases"][0]["validation"] is None
    assert result["ok"] is True
    assert result["result"]["quality_policy"] == "STRICT"
    validation = result["result"]["cases"][0]["validation"]
    assert validation["source_fit"] == "YES"
    assert validation["rule_conformance"] == "CONFORMS"


def test_semantic_agent_rejects_unknown_fields_before_provider(tmp_path):
    root = tmp_path / "store"
    registry = build_default_agent_tool_registry(MemCommitClient(root=root))

    result = registry.invoke(
        MAKEMORE_AGENT_TOOL_NAME,
        {
            "version": MAKEMORE_AGENT_CONTRACT_VERSION,
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
    makemore = registry.invoke(
        MAKEMORE_AGENT_TOOL_NAME,
        {
            "version": MAKEMORE_AGENT_CONTRACT_VERSION,
            "kind": "ground_goal_to_rules",
            "ground_name": "missing-ground",
        },
    )

    assert distill["error"]["code"] == "context_unavailable"
    assert makemore["error"]["code"] == "context_unavailable"
