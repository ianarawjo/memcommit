"""SDK-independent MCP discovery and call projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json

from memcommit.adapters.python_api import HelpDetailReferenceResult
from memcommit.interfaces.agent import (
    AgentToolDefinition,
    AgentToolEffect,
    AgentToolRegistry,
)
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
    use_when: str | None = None
    help_details: tuple[HelpDetailReferenceResult, ...] = ()
    effect: AgentToolEffect | None = None

    def to_dict(self) -> JsonObject:
        value: JsonObject = {
            "name": self.name,
            "description": self.description,
            "inputSchema": _json_object(
                self.input_schema,
                label=f"MCP tool {self.name!r} inputSchema",
            ),
        }
        metadata: JsonObject = {}
        if self.use_when is not None:
            metadata["memcommit/useWhen"] = self.use_when
        if self.help_details:
            metadata["memcommit/helpDetails"] = [
                _help_detail_reference(detail) for detail in self.help_details
            ]
        if metadata:
            value["_meta"] = metadata
        if self.effect is not None:
            value["annotations"] = {
                "readOnlyHint": self.effect.read_only,
                "destructiveHint": self.effect.destructive,
                "idempotentHint": self.effect.idempotent,
                "openWorldHint": self.effect.open_world,
            }
        return value


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
    use_when: str | None
    help_details: tuple[HelpDetailReferenceResult, ...]
    effect: AgentToolEffect | None


def _help_detail_reference(detail: HelpDetailReferenceResult) -> JsonObject:
    value: JsonObject = {
        "id": detail.id,
        "operation": detail.operation,
        "kind": detail.kind,
        "title": detail.title,
        "useWhen": detail.use_when,
        "discovery": detail.discovery,
    }
    if detail.discovery_summary is not None:
        value["discoverySummary"] = detail.discovery_summary
    return value


def _description(
    base: str,
    *,
    use_when: str | None,
    help_details: tuple[HelpDetailReferenceResult, ...],
) -> str:
    paragraphs = [base]
    if use_when is not None:
        paragraphs.append(f"Use when: {use_when}")
    paragraphs.extend(
        f"Selection boundary ({detail.title}): {detail.discovery_summary}"
        for detail in help_details
        if detail.discovery == "TOOL_SELECTION" and detail.discovery_summary is not None
    )
    return "\n\n".join(paragraphs)


def _project_tool(definition: AgentToolDefinition) -> _FrozenMcpTool:
    schema = definition.tool_schema
    name = schema.get("name")
    description = schema.get("description")
    parameters = schema.get("parameters")
    use_when = definition.use_when
    help_details = definition.help_details
    if not isinstance(name, str) or not name.strip():
        raise McpToolProjectionError("Registry tool name must be nonblank text.")
    if not isinstance(description, str) or not description.strip():
        raise McpToolProjectionError(
            f"Registry tool {name!r} description must be nonblank text."
        )
    if use_when is not None and (not isinstance(use_when, str) or not use_when.strip()):
        raise McpToolProjectionError(
            f"Registry tool {name!r} use_when must be nonblank text."
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
        use_when=use_when,
        help_details=help_details,
        effect=definition.effect,
    )


class McpRegistryProjection:
    """Project one frozen agent registry into MCP discovery and call values."""

    def __init__(self, registry: AgentToolRegistry) -> None:
        if not isinstance(registry, AgentToolRegistry):
            raise TypeError("MCP projection requires an AgentToolRegistry.")
        tools = tuple(_project_tool(item) for item in registry.tool_definitions())
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
                description=_description(
                    tool.description,
                    use_when=tool.use_when,
                    help_details=tool.help_details,
                ),
                input_schema=json.loads(tool.input_schema_json),
                use_when=tool.use_when,
                help_details=tool.help_details,
                effect=tool.effect,
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
