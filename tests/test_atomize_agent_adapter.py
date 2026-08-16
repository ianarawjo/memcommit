"""Agent-tool coverage for the structural Atomize public facade."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import memcommit.ops as ops
from memcommit.api import (
    AtomizeAnalysisResult,
    AtomizeAppliedItemResult,
    AtomizeChildResult,
    AtomizeConflictError,
    AtomizeItemResult,
    AtomizeOverviewResult,
    AtomizeOverviewSectionResult,
    AtomizeProviderFailure,
    AtomizeStructuralApplyResult,
    MemCommitClient,
)
from memcommit.interfaces.agent.atomize import (
    ATOMIZE_AGENT_TOOL_NAME,
    AtomizeAgentAdapter,
    atomize_agent_tool_schema,
)
from memcommit.interfaces.agent.registry import build_default_agent_tool_registry
from memcommit.interfaces.mcp import McpRegistryProjection
from memcommit.store import MemoryStore


_PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"
_VERSION = "a" * 64


class _Provider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        assert output_schema is not None
        self.calls += 1
        payload = json.loads(prompt.split(_PAYLOAD_MARKER, 1)[1])
        items = []
        for source in payload["memories"]:
            left, right = source["content"].split(" and ", 1)
            items.append(
                {
                    "candidate_id": source["candidate_id"],
                    "classification": "COMPOSITE",
                    "reason_codes": ["A01_ONE_FOCUS"],
                    "children": [
                        {"content": left, "source_spans": [left]},
                        {"content": right, "source_spans": [right]},
                    ],
                    "reason": "The source contains two independent facts.",
                }
            )
        aliases = [source["candidate_id"] for source in payload["memories"]]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The Memory contains two closing times.",
                        "source_ids": aliases,
                    },
                    "changed": {
                        "text": "The composite Memory will be split.",
                        "source_ids": aliases,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": items,
                "quality_issues": [],
            }
        )


def _proposal() -> AtomizeAnalysisResult:
    section = AtomizeOverviewSectionResult(
        text="Reviewed.",
        source_memory_uids=("memory-1",),
    )
    return AtomizeAnalysisResult(
        analysis_uid="analysis-1",
        version=_VERSION,
        origin="PROVIDER",
        context_uid="context-1",
        context_name="task/source",
        context_digest="b" * 64,
        ruleset_version="rules-v1",
        memory_count=1,
        projected_memory_count=2,
        overview=AtomizeOverviewResult(
            understood=section,
            changed=section,
            unresolved=AtomizeOverviewSectionResult(
                text="",
                source_memory_uids=(),
            ),
        ),
        items=(
            AtomizeItemResult(
                memory_uid="memory-1",
                content="One and two.",
                position=0,
                classification="COMPOSITE",
                action="SPLIT",
                reason_codes=("A01_ONE_FOCUS",),
                children=(
                    AtomizeChildResult(
                        content="One",
                        source_spans=("One",),
                        frame_spans=("One",),
                    ),
                    AtomizeChildResult(
                        content="two.",
                        source_spans=("two.",),
                        frame_spans=("two.",),
                    ),
                ),
                reason="Two independent facts.",
                lint=(),
            ),
        ),
        issues=(),
        workbench_uid="workbench-1",
        output_context_name="task/source",
        in_place_apply_allowed=True,
        _snapshot=object(),  # type: ignore[arg-type]
    )


def _receipt(*, recovered: bool = False) -> AtomizeStructuralApplyResult:
    return AtomizeStructuralApplyResult(
        analysis_uid="analysis-1",
        context_uid="context-1",
        context_name="task/source",
        checkpoint_uid="checkpoint-1",
        split_count=1,
        child_count=2,
        preserved_count=0,
        application_mode="REVIEWED",
        unresolved_at_apply_count=0,
        items=(
            AtomizeAppliedItemResult(
                source_memory_uid="memory-1",
                classification="COMPOSITE",
                result_memory_uids=("child-1", "child-2"),
                result_contents=("One", "two."),
                reason="Two independent facts.",
                reason_codes=("A01_ONE_FOCUS",),
            ),
        ),
        recovered=recovered,
    )


def test_open_calls_one_public_method_and_projects_cache_and_effect(
    tmp_path,
    monkeypatch,
):
    client = MemCommitClient(root=tmp_path / "store")
    calls = []
    monkeypatch.setattr(
        client,
        "open_atomize_analysis",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or _proposal()),
    )

    response = AtomizeAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "open",
            "context_name": "task/source",
            "refresh": True,
            "use_prepared": False,
        }
    )

    assert calls == [
        (
            (),
            {
                "context_name": "task/source",
                "refresh": True,
                "use_prepared": False,
            },
        )
    ]
    assert response["ok"] is True
    result = response["result"]
    assert result["origin"] == "PROVIDER"
    assert result["provider_used"] is True
    assert result["cache_used"] is False
    assert result["effect"] == "DERIVED_SESSION"
    assert result["items"][0]["children"][1]["content"] == "two."
    assert result["apply_as_is"] == {
        "allowed": True,
        "expected_version": _VERSION,
        "provider_used": False,
        "effect": "CONTEXT_CHECKPOINT",
    }
    json.dumps(response)


def test_apply_calls_only_version_bound_public_method_and_projects_receipt(
    tmp_path,
    monkeypatch,
):
    client = MemCommitClient(root=tmp_path / "store")
    calls = []
    monkeypatch.setattr(
        client,
        "apply_saved_atomize_as_is",
        lambda *args, **kwargs: (
            calls.append((args, kwargs)) or _receipt(recovered=True)
        ),
    )

    response = AtomizeAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "apply_as_is",
            "context_name": "task/source",
            "expected_version": _VERSION,
        }
    )

    assert calls == [
        (
            (),
            {"context_name": "task/source", "expected_version": _VERSION},
        )
    ]
    assert response["result"]["checkpoint_uid"] == "checkpoint-1"
    assert response["result"]["recovered"] is True
    assert response["result"]["provider_used"] is False
    assert response["result"]["effect"] == "CONTEXT_CHECKPOINT"


@pytest.mark.parametrize(
    "payload",
    [
        {"version": True, "kind": "open"},
        {"version": 1, "kind": "open", "refresh": 1},
        {"version": 1, "kind": "open", "expected_version": _VERSION},
        {"version": 1, "kind": "apply_as_is"},
        {
            "version": 1,
            "kind": "apply_as_is",
            "expected_version": "A" * 64,
        },
        {"version": 1, "kind": "apply_as_is", "expected_version": "short"},
    ],
)
def test_invalid_contract_stops_before_public_client(tmp_path, monkeypatch, payload):
    client = MemCommitClient(root=tmp_path / "missing-store")
    monkeypatch.setattr(
        client,
        "open_atomize_analysis",
        lambda **kwargs: pytest.fail(f"open was called: {kwargs}"),
    )
    monkeypatch.setattr(
        client,
        "apply_saved_atomize_as_is",
        lambda **kwargs: pytest.fail(f"apply was called: {kwargs}"),
    )

    response = AtomizeAgentAdapter(client).invoke(payload)

    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["retryable"] is False
    assert not (tmp_path / "missing-store").exists()


def test_provider_failure_is_redacted_and_retryable(tmp_path, monkeypatch):
    client = MemCommitClient(root=tmp_path / "store")

    def fail(**kwargs):
        del kwargs
        raise AtomizeProviderFailure("private endpoint and prompt body")

    monkeypatch.setattr(client, "open_atomize_analysis", fail)

    response = AtomizeAgentAdapter(client).invoke({"version": 1, "kind": "open"})

    assert response["error"] == {
        "code": "provider_failure",
        "message": "The Atomize provider failed.",
        "retryable": True,
    }
    assert "endpoint" not in json.dumps(response)


def test_conflict_is_redacted_and_nonretryable(tmp_path, monkeypatch):
    client = MemCommitClient(root=tmp_path / "store")

    def fail(**kwargs):
        del kwargs
        raise AtomizeConflictError("private stale workbench detail")

    monkeypatch.setattr(client, "apply_saved_atomize_as_is", fail)

    response = AtomizeAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "apply_as_is",
            "expected_version": _VERSION,
        }
    )

    assert response["error"] == {
        "code": "stale_state",
        "message": "The accepted Atomize revision changed.",
        "retryable": False,
    }
    assert "workbench" not in json.dumps(response)


def test_schema_is_fresh_strict_and_names_both_effect_boundaries():
    first = atomize_agent_tool_schema()
    first["name"] = "changed"

    schema = atomize_agent_tool_schema()
    branches = schema["parameters"]["oneOf"]
    assert schema["name"] == ATOMIZE_AGENT_TOOL_NAME
    assert [branch["properties"]["kind"]["const"] for branch in branches] == [
        "open",
        "apply_as_is",
    ]
    assert all(branch["additionalProperties"] is False for branch in branches)
    assert branches[1]["properties"]["expected_version"]["pattern"] == (
        "^[0-9a-f]{64}$"
    )
    assert "never calls the provider" in schema["description"]
    assert "checkpoint" in schema["description"]


def test_real_registry_open_saved_apply_and_retry_use_one_provider_and_checkpoint(
    isolated_store,
):
    store = MemoryStore(root=isolated_store)
    context = ops.init("atomize/agent")
    ops.add(context, "The library closes at five and the cafe closes at six.")
    store.save(context)
    store.set_current(context.name)
    provider = _Provider()
    registry = build_default_agent_tool_registry(
        MemCommitClient(
            root=isolated_store,
            semantic_provider_factory=lambda: provider,
        )
    )

    opened = registry.invoke(
        ATOMIZE_AGENT_TOOL_NAME,
        {"version": 1, "kind": "open", "context_name": context.name},
    )
    resumed = registry.invoke(
        ATOMIZE_AGENT_TOOL_NAME,
        {"version": 1, "kind": "open", "context_name": context.name},
    )
    applied = registry.invoke(
        ATOMIZE_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "apply_as_is",
            "context_name": context.name,
            "expected_version": opened["result"]["version"],
        },
    )
    retried = registry.invoke(
        ATOMIZE_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "apply_as_is",
            "context_name": context.name,
            "expected_version": opened["result"]["version"],
        },
    )

    assert opened["result"]["origin"] == "PROVIDER"
    assert opened["result"]["provider_used"] is True
    assert resumed["result"]["origin"] == "SAVED"
    assert resumed["result"]["cache_used"] is True
    assert provider.calls == 1
    assert applied["result"]["recovered"] is False
    assert retried["result"]["recovered"] is True
    assert retried["result"]["checkpoint_uid"] == applied["result"]["checkpoint_uid"]
    assert len(store.list_checkpoints(context.name)) == 1
    assert [memory.content for memory in store.load_direct(context.name).iter_items()] == [
        "The library closes at five",
        "the cafe closes at six.",
    ]


def test_real_registry_rejects_unknown_revision_without_provider_or_checkpoint(
    isolated_store,
):
    store = MemoryStore(root=isolated_store)
    context = ops.init("atomize/stale")
    ops.add(context, "The library closes at five and the cafe closes at six.")
    store.save(context)
    provider = _Provider()
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=lambda: provider,
    )
    client.open_atomize_analysis(context.name)
    registry = build_default_agent_tool_registry(client)

    response = registry.invoke(
        ATOMIZE_AGENT_TOOL_NAME,
        {
            "version": 1,
            "kind": "apply_as_is",
            "context_name": context.name,
            "expected_version": "0" * 64,
        },
    )

    assert response["error"]["code"] == "stale_state"
    assert provider.calls == 1
    assert store.list_checkpoints(context.name) == []


def test_default_registry_projects_and_calls_atomize_through_mcp(
    tmp_path,
    monkeypatch,
):
    client = MemCommitClient(root=tmp_path / "store")
    monkeypatch.setattr(client, "open_atomize_analysis", lambda **kwargs: _proposal())
    projection = McpRegistryProjection(build_default_agent_tool_registry(client))

    definitions = {tool.name: tool for tool in projection.list_tools()}
    result = projection.call_tool(
        ATOMIZE_AGENT_TOOL_NAME,
        {"version": 1, "kind": "open", "context_name": "task/source"},
    )

    assert ATOMIZE_AGENT_TOOL_NAME in definitions
    assert definitions[ATOMIZE_AGENT_TOOL_NAME].input_schema["oneOf"][0][
        "properties"
    ]["kind"] == {"type": "string", "const": "open"}
    assert result.is_error is False
    assert result.structured_content["result"]["analysis_uid"] == "analysis-1"
    assert json.loads(result.content_text) == result.structured_content


def test_adapter_imports_only_public_api_and_shared_agent_contract():
    path = (
        Path(__file__).parents[1]
        / "memcommit"
        / "interfaces"
        / "agent"
        / "atomize.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]

    assert "memcommit.api" in imported
    assert "memcommit.interfaces.agent.contract" in imported
    assert not any(
        name.startswith(
            (
                "memcommit.commands",
                "memcommit.atomize_runtime",
                "memcommit.atomize_application",
                "memcommit.store",
                "memcommit.interfaces.mcp",
            )
        )
        for name in imported
    )
