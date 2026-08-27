"""Optional official-SDK stdio server over the frozen MCP projection."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys
from typing import Any

from memcommit.adapters.python_api import (
    MemCommitClient,
    MemCommitError,
    QueryProviderConfig,
)
from memcommit.adapters.interfaces.agent import build_default_agent_tool_registry
from memcommit.adapters.interfaces.mcp.projection import (
    McpRegistryProjection,
    McpToolCallResult,
)


MCP_SERVER_NAME = "memcommit"
MCP_SDK_INSTALL_HINT = "Install MemCommit with the MCP extra: memcommit[mcp]."


class McpSdkUnavailableError(RuntimeError):
    """The optional official MCP SDK is unavailable."""


def _load_mcp_sdk() -> tuple[Any, Any, Any, Any]:
    try:
        import anyio
        import mcp.types as types
        from mcp.server.lowlevel import Server
        from mcp.server.stdio import stdio_server
    except ImportError as error:
        raise McpSdkUnavailableError(MCP_SDK_INSTALL_HINT) from error
    return anyio, types, Server, stdio_server


def _server_version() -> str:
    try:
        return version("memcommit")
    except PackageNotFoundError:  # pragma: no cover - source-only fallback
        return "0+unknown"


def project_sdk_tools(projection: McpRegistryProjection) -> list[Any]:
    """Create official SDK Tool values from fresh projected definitions."""

    _anyio, types, _server_type, _stdio_server = _load_mcp_sdk()
    projected = []
    for tool in projection.list_tools():
        wire = tool.to_dict()
        raw_annotations = wire.get("annotations")
        annotations = (
            types.ToolAnnotations(**raw_annotations)
            if raw_annotations is not None
            else None
        )
        projected.append(
            types.Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.input_schema,
                annotations=annotations,
                _meta=wire.get("_meta"),
            )
        )
    return projected


def project_sdk_call_result(result: McpToolCallResult) -> Any:
    """Create one official SDK result without reinterpreting its envelope."""

    if not isinstance(result, McpToolCallResult):
        raise TypeError("SDK call-result projection requires McpToolCallResult.")
    _anyio, types, _server_type, _stdio_server = _load_mcp_sdk()
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=result.content_text)],
        structuredContent=result.structured_content,
        isError=result.is_error,
    )


def build_mcp_server(projection: McpRegistryProjection) -> Any:
    """Bind one projection to the official v2 low-level MCP Server."""

    if not isinstance(projection, McpRegistryProjection):
        raise TypeError("MCP server requires an McpRegistryProjection.")
    anyio, types, Server, _stdio_server = _load_mcp_sdk()

    async def list_tools(_context: Any, _params: Any) -> Any:
        return types.ListToolsResult(tools=project_sdk_tools(projection))

    async def call_tool(_context: Any, params: Any) -> Any:
        # Provider and Store calls are synchronous. Shield the worker until it
        # returns so cancellation cannot abandon an in-flight mutation while
        # the event loop remains available for protocol housekeeping.
        projected = await anyio.to_thread.run_sync(
            lambda: projection.call_tool(params.name, params.arguments or {}),
            abandon_on_cancel=False,
        )
        return project_sdk_call_result(projected)

    return Server(
        MCP_SERVER_NAME,
        version=_server_version(),
        instructions=(
            "Use the explicit versioned MemCommit tool schemas. Tool responses "
            "contain the complete operation receipt or bounded public error."
        ),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def serve_stdio(projection: McpRegistryProjection) -> None:
    """Run one official MCP stdio session until its transport closes."""

    _anyio, _types, _server_type, stdio_server = _load_mcp_sdk()
    server = build_mcp_server(projection)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mem-mcp",
        description="Serve registered MemCommit agent tools over MCP stdio.",
    )
    store = parser.add_mutually_exclusive_group()
    store.add_argument(
        "--root",
        type=Path,
        help="Use one explicit existing MemCommit Store root.",
    )
    store.add_argument(
        "--profile",
        help="Use one configured MemCommit Profile instead of the active Profile.",
    )
    parser.add_argument(
        "--model",
        help="Override the frozen Query provider model for this server process.",
    )
    parser.add_argument(
        "--reasoning-effort",
        help="Override the frozen Query reasoning effort for this server process.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        help="Override the positive Query provider timeout for this server process.",
    )
    return parser


def _projection_from_args(arguments: argparse.Namespace) -> McpRegistryProjection:
    defaults = QueryProviderConfig()
    query_config = QueryProviderConfig(
        model=arguments.model or defaults.model,
        reasoning_effort=arguments.reasoning_effort or defaults.reasoning_effort,
        timeout_seconds=(
            arguments.timeout_seconds
            if arguments.timeout_seconds is not None
            else defaults.timeout_seconds
        ),
    )
    client = MemCommitClient(
        root=arguments.root,
        profile=arguments.profile,
        query_config=query_config,
    )
    return McpRegistryProjection(build_default_agent_tool_registry(client))


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point for the optional MCP stdio server."""

    arguments = _parser().parse_args(argv)
    try:
        anyio, _types, _server_type, _stdio_server = _load_mcp_sdk()
        projection = _projection_from_args(arguments)
        anyio.run(serve_stdio, projection)
    except (
        McpSdkUnavailableError,
        MemCommitError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        print(f"mem-mcp: {error}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "MCP_SDK_INSTALL_HINT",
    "MCP_SERVER_NAME",
    "McpSdkUnavailableError",
    "build_mcp_server",
    "main",
    "project_sdk_call_result",
    "project_sdk_tools",
    "serve_stdio",
]


if __name__ == "__main__":  # pragma: no cover - module execution convenience
    raise SystemExit(main())
