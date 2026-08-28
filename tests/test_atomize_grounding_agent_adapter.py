"""Agent-tool coverage for the public Atomize Grounding facade."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from memcommit.adapters.python_api import (
    AtomizeGroundingApplyResult,
    AtomizeGroundingProviderFailure,
    AtomizeGroundingProposalResult,
    AtomizeGroundingQuestionResult,
    AtomizeGroundingSessionResult,
    MemCommitClient,
)
from memcommit.adapters.agent.atomize_grounding import (
    ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
    AtomizeGroundingAgentAdapter,
    atomize_grounding_agent_tool_schema,
)
from memcommit.adapters.agent.registry import build_default_agent_tool_registry


def _client(tmp_path) -> MemCommitClient:
    return MemCommitClient(root=tmp_path / "store", create=True)


def _session() -> AtomizeGroundingSessionResult:
    return AtomizeGroundingSessionResult(
        session_uid="dialogue-1",
        version="saved-version",
        context_name="task/source",
        state="READY_TO_APPLY",
        issue_uid="ambiguity:1",
        issue_kind="AMBIGUITY",
        arity="UNARY",
        turn_count=2,
        active_understanding=("The Memory concerns physical cards.",),
        current_status="RESOLVED",
        current_explanation="The latest answer chose one reading.",
        questions=(
            AtomizeGroundingQuestionResult(
                uid="question-1",
                kind="CLARIFICATION",
                priority="REQUIRED",
                text="Does this mean a physical card?",
                reason="The original wording is ambiguous.",
                issue_uids=("ambiguity:1",),
            ),
        ),
        proposals=(
            AtomizeGroundingProposalResult(
                uid="proposal-1",
                operation="UPDATE",
                necessity="REQUIRED",
                memory_uid="memory-1",
                content="Use a physical NFC card after 5 p.m.",
                reason="Makes the accepted reading explicit.",
                issue_uids=("ambiguity:1",),
            ),
        ),
        ready_to_apply=True,
        checkpoint_uid=None,
    )


@pytest.mark.parametrize(
    ("kind", "payload", "method_name", "expected_arguments"),
    [
        (
            "open",
            {"version": 1, "kind": "open", "context_name": "task/source"},
            "open_atomize_grounding",
            {"context_name": "task/source"},
        ),
        (
            "start",
            {
                "version": 1,
                "kind": "start",
                "selector": "1",
                "comment": "Use the physical-card reading.",
            },
            "start_atomize_grounding",
            {
                "selector": "1",
                "comment": "Use the physical-card reading.",
                "context_name": None,
            },
        ),
        (
            "reply",
            {
                "version": 1,
                "kind": "reply",
                "reply": "That is correct.",
                "revision": "confirm",
            },
            "reply_atomize_grounding",
            {
                "reply": "That is correct.",
                "context_name": None,
                "revision": "CONFIRM",
            },
        ),
        (
            "keep",
            {"version": 1, "kind": "keep"},
            "keep_atomize_grounding",
            {"context_name": None},
        ),
    ],
)
def test_each_nonapply_action_calls_one_public_client_method(
    tmp_path,
    monkeypatch,
    kind,
    payload,
    method_name,
    expected_arguments,
):
    client = _client(tmp_path)
    calls = []
    monkeypatch.setattr(
        client,
        method_name,
        lambda *args, **kwargs: (calls.append((args, kwargs)) or _session()),
    )

    result = AtomizeGroundingAgentAdapter(client).invoke(payload)

    assert result["ok"] is True
    assert result["kind"] == kind
    assert result["result"]["session"]["session_uid"] == "dialogue-1"
    assert result["result"]["session"]["active_understanding"] == [
        "The Memory concerns physical cards."
    ]
    assert result["result"]["session"]["questions"][0]["issue_uids"] == ["ambiguity:1"]
    assert result["result"]["session"]["proposals"][0]["operation"] == "UPDATE"
    assert calls == [((), expected_arguments)]
    json.dumps(result)


def test_apply_returns_checkpoint_change_and_recovery_receipt(tmp_path, monkeypatch):
    client = _client(tmp_path)
    calls = []
    monkeypatch.setattr(
        client,
        "apply_atomize_grounding",
        lambda *args, **kwargs: (
            calls.append((args, kwargs))
            or AtomizeGroundingApplyResult(
                session=_session(),
                checkpoint_uid="checkpoint-1",
                change_count=2,
                recovered=True,
            )
        ),
    )

    result = AtomizeGroundingAgentAdapter(client).invoke(
        {"version": 1, "kind": "apply", "context_name": "task/source"}
    )

    assert result["ok"] is True
    assert result["result"]["checkpoint_uid"] == "checkpoint-1"
    assert result["result"]["change_count"] == 2
    assert result["result"]["recovered"] is True
    assert calls == [((), {"context_name": "task/source"})]


@pytest.mark.parametrize(
    "payload",
    [
        {"version": True, "kind": "open"},
        {"version": 1, "kind": "start", "selector": "1"},
        {"version": 1, "kind": "open", "reply": "not valid here"},
        {
            "version": 1,
            "kind": "reply",
            "reply": "Use it.",
            "revision": "REWRITE",
        },
    ],
)
def test_invalid_action_contract_stops_before_public_client(
    tmp_path,
    monkeypatch,
    payload,
):
    client = _client(tmp_path)
    monkeypatch.setattr(
        client,
        "open_atomize_grounding",
        lambda **kwargs: pytest.fail(f"public method was called: {kwargs}"),
    )

    result = AtomizeGroundingAgentAdapter(client).invoke(payload)

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"
    assert result["error"]["retryable"] is False


def test_provider_failure_is_redacted_and_retryable(tmp_path, monkeypatch):
    client = _client(tmp_path)

    def fail(**kwargs):
        del kwargs
        raise AtomizeGroundingProviderFailure("private endpoint and prompt body")

    monkeypatch.setattr(client, "reply_atomize_grounding", fail)

    result = AtomizeGroundingAgentAdapter(client).invoke(
        {"version": 1, "kind": "reply", "reply": "Continue."}
    )

    assert result["error"] == {
        "code": "provider_failure",
        "message": "The Atomize Grounding provider failed.",
        "retryable": True,
    }
    assert "endpoint" not in json.dumps(result)


def test_schema_is_fresh_strict_and_uses_stable_tool_name():
    first = atomize_grounding_agent_tool_schema()
    first["name"] = "changed"

    schema = atomize_grounding_agent_tool_schema()
    assert schema["name"] == ATOMIZE_GROUNDING_AGENT_TOOL_NAME
    assert [
        branch["properties"]["kind"]["const"]
        for branch in schema["parameters"]["oneOf"]
    ] == [
        "open",
        "start",
        "reply",
        "keep",
        "apply",
    ]
    assert all(
        branch["additionalProperties"] is False
        for branch in schema["parameters"]["oneOf"]
    )


def test_default_registry_discovers_and_calls_grounding(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    monkeypatch.setattr(client, "open_atomize_grounding", lambda **kwargs: _session())
    registry = build_default_agent_tool_registry(client)

    definitions = {
        definition.tool_schema["name"]: definition
        for definition in registry.tool_definitions()
    }
    result = registry.invoke(
        ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
        {"version": 1, "kind": "open", "context_name": "task/source"},
    )

    assert ATOMIZE_GROUNDING_AGENT_TOOL_NAME in definitions
    parameters = definitions[ATOMIZE_GROUNDING_AGENT_TOOL_NAME].tool_schema[
        "parameters"
    ]
    assert parameters["oneOf"][0]["properties"]["kind"] == {
        "type": "string",
        "const": "open",
    }
    assert result["ok"] is True
    assert result["result"]["session"]["issue_uid"] == "ambiguity:1"


def test_adapter_imports_only_public_api_and_shared_agent_contract():
    path = (
        Path(__file__).parents[1]
        / "src" / "memcommit"
        / "adapters"
        / "agent"
        / "atomize_grounding.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]

    assert "memcommit.adapters.python_api" in imported
    assert "memcommit.adapters.agent.contract" in imported
    assert not any(
        name.startswith(
            (
                "memcommit.adapters.console.commands",
                "memcommit.atomize_grounding_application",
                "memcommit.atomize_grounding_runtime",
                "memcommit.application.operations.atomize.grounding_application",
                "memcommit.application.operations.atomize.grounding_runtime",
                "memcommit.store",
            )
        )
        for name in imported
    )
