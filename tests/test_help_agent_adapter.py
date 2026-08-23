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
    assert response["result"]["count"] == 64
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
            "Add Source-only items to a selected Target, leave exact matches "
            "unchanged, and choose Source or Target for stored-item conflicts."
        ),
        "flow": "Source Context -> selected Target Context",
        "execution": "DETERMINISTIC",
        "effect": (
            "Changes Target only after every required conflict has KEEP TARGET "
            "or TAKE SOURCE; Source stays unchanged"
        ),
        "range": "Exact roots or matching descendants by the same relative path",
        "best_for": (
            "Appending Source-only items or bringing a copied or branched "
            "Context into a selected Target Context without semantic synthesis."
        ),
        "use_when": (
            "Appending Source-only items or bringing a copied or branched "
            "Context into a selected Target Context without semantic synthesis."
        ),
        "maturity": None,
        "details": [
            {
                "id": "structural-boundary",
                "operation": "merge",
                "kind": "COMPARISON",
                "title": "MERGE BOUNDARY",
                "use_when": (
                    "Checking how each structural Source/Target case is handled."
                ),
                "discovery": "ON_DEMAND",
                "discovery_summary": None,
            }
        ],
    }
    assert response["result"]["effect"] == "NONE"


def test_describe_add_returns_use_when_and_compact_detail_reference(tmp_path):
    adapter = HelpAgentAdapter(MemCommitClient(root=tmp_path / "missing-store"))

    response = adapter.invoke({"version": 1, "kind": "describe", "operation": "add"})

    operation = response["result"]["operation"]
    assert operation["use_when"] == operation["best_for"]
    [reference] = operation["details"]
    assert reference["id"] == "copy-or-link"
    assert "options" not in reference

    comparison = adapter.invoke(
        {
            "version": 1,
            "kind": "describe-detail",
            "operation": "add",
            "detail": "copy-or-link",
        }
    )["result"]["detail"]
    assert [option["label"] for option in comparison["options"]] == [
        "INDEPENDENT WORK",
        "EXACT MEMORY OR CONTEXT",
        "LIVE MEMORY",
        "LIVE CONTEXT",
    ]


def test_import_limitation_and_query_access_boundary_are_addressable(tmp_path):
    adapter = HelpAgentAdapter(MemCommitClient(root=tmp_path / "missing-store"))

    imported = adapter.invoke(
        {"version": 1, "kind": "describe", "operation": "import"}
    )["result"]["operation"]
    limitation = adapter.invoke(
        {
            "version": 1,
            "kind": "describe-detail",
            "operation": "import",
            "detail": "current-limitation",
        }
    )
    access = adapter.invoke(
        {
            "version": 1,
            "kind": "describe-detail",
            "operation": "query",
            "detail": "query-only-access",
        }
    )

    assert imported["maturity"] == "PARTIAL"
    assert imported["details"][0]["kind"] == "LIMITATION"
    assert limitation["ok"] is True
    assert limitation["result"]["detail"]["title"] == "CURRENT LIMITATION"
    assert "MemCommit-to-MemCommit" in limitation["result"]["detail"]["body"]
    assert access["ok"] is True
    assert access["result"]["detail"]["kind"] == "ACCESS_BOUNDARY"
    assert "QUERY without READ" in access["result"]["detail"]["body"]


def test_agent_can_list_compact_detail_ids_before_requesting_one(tmp_path):
    adapter = HelpAgentAdapter(MemCommitClient(root=tmp_path / "missing-store"))

    response = adapter.invoke(
        {"version": 1, "kind": "list-details", "operation": "add"}
    )

    assert response["ok"] is True
    assert response["result"]["operation"] == "add"
    assert response["result"]["count"] == 1
    [detail] = response["result"]["details"]
    assert detail["id"] == "copy-or-link"
    assert detail["discovery"] == "TOOL_SELECTION"
    assert "options" not in detail


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"version": True, "kind": "list"},
        {"version": 1, "kind": "unknown"},
        {"version": 1, "kind": "list", "operation": "help"},
        {"version": 1, "kind": "describe"},
        {"version": 1, "kind": "describe", "operation": "unknown"},
        {"version": 1, "kind": "list-details"},
        {"version": 1, "kind": "describe-detail", "operation": "add"},
        {
            "version": 1,
            "kind": "describe-detail",
            "operation": "init",
            "detail": "copy-or-link",
        },
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
    assert schema["parameters"]["allOf"][0]["then"] == {
        "not": {"required": ["operation"]}
    }
    assert schema["parameters"]["allOf"][0]["else"] == {"required": ["operation"]}
    assert len(schema["parameters"]["properties"]["operation"]["enum"]) == 64
    assert schema["parameters"]["properties"]["detail"]["enum"] == [
        "actions",
        "copy-or-link",
        "current-limitation",
        "distill-or-atomize",
        "evaluation-scope",
        "fit-or-conformance",
        "history-routes",
        "interactive-commands",
        "invocation",
        "management-actions",
        "materialization-routes",
        "operation-routes",
        "parent-contexts",
        "partial-overlap",
        "query-only-access",
        "selection-routes",
        "structural-boundary",
        "update-vs-meld",
        "verdicts",
    ]
    assert schema["parameters"]["allOf"][1]["then"] == {"required": ["detail"]}
    assert "use-when guidance" in schema["description"]
    assert "individually addressable typed details" in schema["description"]
    json.dumps(schema)
