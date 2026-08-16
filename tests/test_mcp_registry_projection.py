"""SDK-independent MCP projection tests over the frozen agent registry."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from memcommit.api import MemCommitClient
from memcommit.interfaces.agent import (
    ADD_AGENT_TOOL_NAME,
    ATOMIZE_AGENT_TOOL_NAME,
    ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
    COMPARE_AGENT_TOOL_NAME,
    DEDUP_AGENT_TOOL_NAME,
    DISTILL_AGENT_TOOL_NAME,
    ELABORATE_AGENT_TOOL_NAME,
    FIT_AGENT_TOOL_NAME,
    HELP_AGENT_TOOL_NAME,
    MELD_AGENT_TOOL_NAME,
    QUALITY_FIND_AGENT_TOOL_NAME,
    QUERY_AGENT_TOOL_NAME,
    RESOLVE_AGENT_TOOL_NAME,
    AgentToolBinding,
    AgentToolRegistry,
    build_default_agent_tool_registry,
)
from memcommit.interfaces.mcp import (
    McpRegistryProjection,
    McpToolDefinition,
    McpToolProjectionError,
)


def _binding(*, schema=None, handler=None) -> AgentToolBinding:
    return AgentToolBinding(
        name="example_tool",
        schema_factory=lambda: schema
        or {
            "name": "example_tool",
            "description": "Example tool.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"text": {"type": "string"}},
            },
        },
        handler=handler or (lambda payload: {"ok": True, "result": payload}),
    )


def test_default_registry_projects_parameters_to_fresh_mcp_input_schemas(tmp_path):
    registry = build_default_agent_tool_registry(
        MemCommitClient(root=tmp_path / "store")
    )
    projection = McpRegistryProjection(registry)

    first = projection.list_tools()
    second = projection.list_tools()

    assert first is not second
    assert tuple(tool.name for tool in first) == (
        HELP_AGENT_TOOL_NAME,
        QUERY_AGENT_TOOL_NAME,
        QUALITY_FIND_AGENT_TOOL_NAME,
        ADD_AGENT_TOOL_NAME,
        COMPARE_AGENT_TOOL_NAME,
        MELD_AGENT_TOOL_NAME,
        ATOMIZE_AGENT_TOOL_NAME,
        ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
        DISTILL_AGENT_TOOL_NAME,
        ELABORATE_AGENT_TOOL_NAME,
        FIT_AGENT_TOOL_NAME,
        RESOLVE_AGENT_TOOL_NAME,
        DEDUP_AGENT_TOOL_NAME,
    )
    registry_schemas = registry.tool_schemas()
    for tool, schema in zip(first, registry_schemas, strict=True):
        assert tool.description == schema["description"]
        assert tool.input_schema == schema["parameters"]
        wire = tool.to_dict()
        assert wire["inputSchema"] == schema["parameters"]
        assert "parameters" not in wire
        json.dumps(wire)

    first[0].input_schema["type"] = "changed"
    assert projection.list_tools()[0].input_schema["type"] == "object"


def test_successful_call_preserves_structured_and_text_envelopes():
    calls: list[object] = []

    def handler(payload):
        calls.append(payload)
        return {
            "version": 7,
            "ok": True,
            "kind": "example",
            "result": {"echo": payload},
        }

    projection = McpRegistryProjection(AgentToolRegistry((_binding(handler=handler),)))
    arguments = {"text": "hello\nworld"}

    result = projection.call_tool("example_tool", arguments)

    assert calls == [arguments]
    assert result.is_error is False
    assert json.loads(result.content_text) == result.structured_content
    assert result.structured_content == {
        "version": 7,
        "ok": True,
        "kind": "example",
        "result": {"echo": arguments},
    }


def test_operation_and_registry_failures_are_mcp_errors_without_rewriting():
    operation_error = {
        "version": 1,
        "ok": False,
        "kind": "example",
        "error": {
            "code": "authority_denied",
            "message": "Denied.",
            "retryable": False,
        },
    }
    projection = McpRegistryProjection(
        AgentToolRegistry((_binding(handler=lambda _payload: operation_error),))
    )

    denied = projection.call_tool("example_tool", {})
    unknown = projection.call_tool("missing_tool", {})

    assert denied.is_error is True
    assert denied.structured_content == operation_error
    assert json.loads(denied.content_text) == operation_error
    assert unknown.is_error is True
    assert unknown.structured_content["error"]["code"] == "unknown_tool"
    assert unknown.structured_content["error"]["retryable"] is False


@pytest.mark.parametrize(
    ("schema", "message"),
    [
        (
            {
                "name": "example_tool",
                "description": "",
                "parameters": {"type": "object"},
            },
            "description",
        ),
        (
            {
                "name": "example_tool",
                "description": "Example.",
            },
            "parameters",
        ),
    ],
)
def test_unprojectable_registry_schema_fails_before_transport_start(schema, message):
    registry = AgentToolRegistry((_binding(schema=schema),))

    with pytest.raises(McpToolProjectionError, match=message):
        McpRegistryProjection(registry)


def test_manual_tool_definition_rejects_nested_nontext_schema_keys():
    definition = McpToolDefinition(
        name="example_tool",
        description="Example.",
        input_schema={"nested": {1: "not a text key"}},
    )

    with pytest.raises(McpToolProjectionError, match="text keys"):
        definition.to_dict()


def test_projection_has_no_sdk_terminal_or_runtime_dependency():
    path = (
        Path(__file__).parents[1] / "memcommit" / "interfaces" / "mcp" / "projection.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "mcp",
        "memcommit.commands",
        "memcommit.operations",
        "memcommit.infrastructure",
        "memcommit.store",
        "typer",
        "prompt_toolkit",
    )
    assert not any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in imported
        for prefix in forbidden
    )
