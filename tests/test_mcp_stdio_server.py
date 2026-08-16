"""Official MCP SDK binding tests for the optional stdio server."""

from __future__ import annotations

import ast
from importlib.metadata import version
import json
from pathlib import Path
import tomllib

import anyio
import pytest

from memcommit.api import HelpDetailReferenceResult
from memcommit.interfaces.agent import AgentToolBinding, AgentToolRegistry
from memcommit.interfaces.mcp import McpRegistryProjection
from memcommit.interfaces.mcp.server import (
    MCP_SERVER_NAME,
    build_mcp_server,
    main,
    project_sdk_call_result,
    project_sdk_tools,
)


mcp = pytest.importorskip("mcp")


def _projection(*, handler=None) -> McpRegistryProjection:
    schema = {
        "name": "example_tool",
        "description": "Return one versioned example envelope.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"text": {"type": "string"}},
        },
    }
    binding = AgentToolBinding(
        name="example_tool",
        schema_factory=lambda: schema,
        use_when="Returning one bounded example envelope.",
        help_details=(
            HelpDetailReferenceResult(
                id="choose-example",
                operation="help",
                kind="COMPARISON",
                title="CHOOSE EXAMPLE",
                use_when="Choosing the example tool.",
                discovery="TOOL_SELECTION",
                discovery_summary="Use this example only for bounded envelopes.",
            ),
        ),
        handler=handler
        or (
            lambda payload: {
                "version": 1,
                "ok": True,
                "kind": "example",
                "result": payload,
            }
        ),
    )
    return McpRegistryProjection(AgentToolRegistry((binding,)))


def test_sdk_values_preserve_frozen_schema_and_complete_result_envelope():
    projection = _projection()

    tools = project_sdk_tools(projection)
    projected = projection.call_tool("example_tool", {"text": "hello"})
    result = project_sdk_call_result(projected)

    assert len(tools) == 1
    assert tools[0].name == "example_tool"
    assert "Use when: Returning one bounded example envelope." in tools[0].description
    assert tools[0].description.endswith(
        "Selection boundary (CHOOSE EXAMPLE): Use this example only for bounded "
        "envelopes."
    )
    assert tools[0].meta == {
        "memcommit/useWhen": "Returning one bounded example envelope.",
        "memcommit/helpDetails": [
            {
                "id": "choose-example",
                "operation": "help",
                "kind": "COMPARISON",
                "title": "CHOOSE EXAMPLE",
                "useWhen": "Choosing the example tool.",
                "discovery": "TOOL_SELECTION",
                "discoverySummary": "Use this example only for bounded envelopes.",
            }
        ],
    }
    assert tools[0].input_schema == projection.list_tools()[0].input_schema
    assert result.is_error is False
    assert result.structured_content == projected.structured_content
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    assert json.loads(result.content[0].text) == result.structured_content


def test_v2_client_discovers_and_calls_the_low_level_server_in_memory():
    from mcp.client._memory import InMemoryTransport
    from mcp.client.session import ClientSession

    projection = _projection()
    server = build_mcp_server(projection)

    async def exercise() -> None:
        async with InMemoryTransport(server, raise_exceptions=True) as streams:
            async with ClientSession(*streams) as session:
                initialized = await session.initialize()
                listed = await session.list_tools()
                called = await session.call_tool(
                    "example_tool",
                    {"text": "through MCP"},
                )
                unknown = await session.call_tool("missing_tool", {})

        assert initialized.server_info.name == MCP_SERVER_NAME
        assert [tool.name for tool in listed.tools] == ["example_tool"]
        assert "Use when: Returning one bounded example envelope." in (
            listed.tools[0].description
        )
        assert listed.tools[0].description.endswith(
            "Selection boundary (CHOOSE EXAMPLE): Use this example only for "
            "bounded envelopes."
        )
        assert listed.tools[0].meta == {
            "memcommit/useWhen": "Returning one bounded example envelope.",
            "memcommit/helpDetails": [
                {
                    "id": "choose-example",
                    "operation": "help",
                    "kind": "COMPARISON",
                    "title": "CHOOSE EXAMPLE",
                    "useWhen": "Choosing the example tool.",
                    "discovery": "TOOL_SELECTION",
                    "discoverySummary": (
                        "Use this example only for bounded envelopes."
                    ),
                }
            ],
        }
        assert listed.tools[0].input_schema == projection.list_tools()[0].input_schema
        assert called.is_error is False
        assert called.structured_content["result"] == {"text": "through MCP"}
        assert unknown.is_error is True
        assert unknown.structured_content["error"]["code"] == "unknown_tool"
        assert unknown.structured_content["error"]["retryable"] is False

    anyio.run(exercise)


def test_mcp_entrypoint_and_v2_sdk_remain_an_optional_distribution_surface():
    root = Path(__file__).parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"]["mem-mcp"] == (
        "memcommit.interfaces.mcp.server:main"
    )
    assert metadata["project"]["optional-dependencies"]["mcp"] == ["mcp>=2,<3"]
    assert version("mcp").split(".", 1)[0] == "2"


def test_server_source_is_a_thin_transport_adapter():
    path = Path(__file__).parents[1] / "memcommit" / "interfaces" / "mcp" / "server.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "memcommit.commands",
        "memcommit.operations",
        "memcommit.infrastructure",
        "memcommit.store",
        "prompt_toolkit",
        "typer",
    )
    assert not any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in imported
        for prefix in forbidden
    )


def test_invalid_process_configuration_fails_before_transport_start(capsys):
    assert main(["--timeout-seconds", "0"]) == 2
    assert "timeout must be positive" in capsys.readouterr().err
