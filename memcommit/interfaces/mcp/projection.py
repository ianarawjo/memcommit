"""SDK-independent MCP discovery and call projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json

from memcommit.interfaces.agent import AgentToolRegistry
from memcommit.interfaces.agent.contract import JsonObject


class McpToolProjectionError(ValueError):
    """A frozen registry schema cannot be represented as an MCP tool."""


def _has_only_text_object_keys(value: object) -> bool:
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _has_only_text_object_keys(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_has_only_text_object_keys(item) for item in value)
    return True


def _json_object(value: object, *, label: str) -> JsonObject:
    if not isinstance(value, Mapping) or not _has_only_text_object_keys(value):
        raise McpToolProjectionError(f"{label} must be an object with text keys.")
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        decoded = json.loads(serialized)
    except (TypeError, ValueError) as error:
        raise McpToolProjectionError(f"{label} must be JSON-safe.") from error
    if not isinstance(decoded, dict):
        raise McpToolProjectionError(f"{label} must decode to an object.")
    return decoded


@dataclass(frozen=True)
class McpToolDefinition:
    """One protocol-shaped tool without an SDK object dependency."""

    name: str
    description: str
    input_schema: JsonObject

    def to_dict(self) -> JsonObject:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": _json_object(
                self.input_schema,
                label=f"MCP tool {self.name!r} inputSchema",
            ),
        }


@dataclass(frozen=True)
class McpToolCallResult:
    """Structured and human-readable projections of one registry response."""

    content_text: str
    structured_content: JsonObject
    is_error: bool


@dataclass(frozen=True)
class _FrozenMcpTool:
    name: str
    description: str
    input_schema_json: str


def _project_tool(schema: JsonObject) -> _FrozenMcpTool:
    name = schema.get("name")
    description = schema.get("description")
    parameters = schema.get("parameters")
    if not isinstance(name, str) or not name.strip():
        raise McpToolProjectionError("Registry tool name must be nonblank text.")
    if not isinstance(description, str) or not description.strip():
        raise McpToolProjectionError(
            f"Registry tool {name!r} description must be nonblank text."
        )
    input_schema = _json_object(
        parameters,
        label=f"Registry tool {name!r} parameters",
    )
    return _FrozenMcpTool(
        name=name,
        description=description,
        input_schema_json=json.dumps(
            input_schema,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


class McpRegistryProjection:
    """Project one frozen agent registry into MCP discovery and call values."""

    def __init__(self, registry: AgentToolRegistry) -> None:
        if not isinstance(registry, AgentToolRegistry):
            raise TypeError("MCP projection requires an AgentToolRegistry.")
        tools = tuple(_project_tool(schema) for schema in registry.tool_schemas())
        if tuple(tool.name for tool in tools) != registry.tool_names:
            raise McpToolProjectionError(
                "Projected MCP tool order must match the frozen registry."
            )
        self._registry = registry
        self._tools = tools

    def list_tools(self) -> tuple[McpToolDefinition, ...]:
        """Return fresh MCP-shaped definitions for frozen registry tools."""

        return tuple(
            McpToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=json.loads(tool.input_schema_json),
            )
            for tool in self._tools
        )

    def call_tool(self, name: object, arguments: object) -> McpToolCallResult:
        """Dispatch one decoded MCP call and preserve its complete envelope."""

        response = self._registry.invoke(name, arguments)
        content_text = json.dumps(
            response,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return McpToolCallResult(
            content_text=content_text,
            structured_content=json.loads(content_text),
            is_error=response.get("ok") is not True,
        )


__all__ = [
    "McpRegistryProjection",
    "McpToolCallResult",
    "McpToolDefinition",
    "McpToolProjectionError",
]
