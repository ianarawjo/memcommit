"""Frozen in-process registry for versioned MemCommit agent tools."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import json
from types import MappingProxyType

from memcommit.api import MemCommitClient
from memcommit.interfaces.agent.add import (
    ADD_AGENT_TOOL_NAME,
    AddAgentAdapter,
    add_agent_tool_schema,
)
from memcommit.interfaces.agent.atomize_grounding import (
    ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
    AtomizeGroundingAgentAdapter,
    atomize_grounding_agent_tool_schema,
)
from memcommit.interfaces.agent.atomize import (
    ATOMIZE_AGENT_TOOL_NAME,
    AtomizeAgentAdapter,
    atomize_agent_tool_schema,
)
from memcommit.interfaces.agent.contract import JsonObject, error_response
from memcommit.interfaces.agent.distill import (
    DISTILL_AGENT_TOOL_NAME,
    DistillAgentAdapter,
    distill_agent_tool_schema,
)
from memcommit.interfaces.agent.elaborate import (
    ELABORATE_AGENT_TOOL_NAME,
    ElaborateAgentAdapter,
    elaborate_agent_tool_schema,
)
from memcommit.interfaces.agent.fit import (
    FIT_AGENT_TOOL_NAME,
    FitAgentAdapter,
    fit_agent_tool_schema,
)
from memcommit.interfaces.agent.query import (
    QUERY_AGENT_TOOL_NAME,
    QueryAgentAdapter,
    query_agent_tool_schema,
)
from memcommit.interfaces.agent.meld import (
    MELD_AGENT_TOOL_NAME,
    MeldAgentAdapter,
    meld_agent_tool_schema,
)


AGENT_TOOL_REGISTRY_VERSION = 1
AgentToolSchemaFactory = Callable[[], JsonObject]
AgentToolHandler = Callable[[object], JsonObject]


class AgentToolRegistrationError(ValueError):
    """A host supplied an invalid or duplicate tool binding."""


@dataclass(frozen=True)
class AgentToolBinding:
    """One schema factory and decoded-payload handler owned by a host."""

    name: str
    schema_factory: AgentToolSchemaFactory
    handler: AgentToolHandler


@dataclass(frozen=True)
class _FrozenAgentTool:
    name: str
    schema_json: str
    handler: AgentToolHandler


def _has_only_text_object_keys(value: object) -> bool:
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _has_only_text_object_keys(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_has_only_text_object_keys(item) for item in value)
    return True


def _registration_schema(binding: AgentToolBinding) -> str:
    if not isinstance(binding.name, str) or not binding.name.strip():
        raise AgentToolRegistrationError("Agent tool name must be nonblank text.")
    if not callable(binding.schema_factory):
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} schema_factory must be callable."
        )
    if not callable(binding.handler):
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} handler must be callable."
        )
    try:
        schema = binding.schema_factory()
    except Exception as error:
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} schema_factory failed."
        ) from error
    if not isinstance(schema, Mapping) or not _has_only_text_object_keys(schema):
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} schema must be an object with text keys."
        )
    if schema.get("name") != binding.name:
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} schema name must match its binding."
        )
    try:
        # Store a canonical JSON snapshot so discovery cannot mutate the
        # registered schema and later factory changes cannot alter this host.
        return json.dumps(
            schema,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} schema must be JSON-safe."
        ) from error


def _registry_error(*, code: str, message: str) -> JsonObject:
    return error_response(
        version=AGENT_TOOL_REGISTRY_VERSION,
        kind=None,
        code=code,
        message=message,
        retryable=False,
    )


class AgentToolRegistry:
    """Discover and invoke one frozen set of decoded-payload tools."""

    def __init__(self, bindings: Iterable[AgentToolBinding] = ()) -> None:
        frozen: dict[str, _FrozenAgentTool] = {}
        for binding in bindings:
            if not isinstance(binding, AgentToolBinding):
                raise AgentToolRegistrationError(
                    "Registry entries must be AgentToolBinding values."
                )
            if binding.name in frozen:
                raise AgentToolRegistrationError(
                    f"Agent tool {binding.name!r} is registered more than once."
                )
            frozen[binding.name] = _FrozenAgentTool(
                name=binding.name,
                schema_json=_registration_schema(binding),
                handler=binding.handler,
            )
        self._tools = MappingProxyType(frozen)

    @property
    def tool_names(self) -> tuple[str, ...]:
        """Return the deterministic registration order."""

        return tuple(self._tools)

    def tool_schemas(self) -> tuple[JsonObject, ...]:
        """Return fresh JSON objects for the frozen registered schemas."""

        return tuple(json.loads(tool.schema_json) for tool in self._tools.values())

    def invoke(self, tool_name: object, payload: object) -> JsonObject:
        """Invoke one known tool with an already decoded JSON-compatible payload."""

        if not isinstance(tool_name, str) or not tool_name.strip():
            return _registry_error(
                code="invalid_tool_name",
                message="Agent tool name must be nonblank text.",
            )
        tool = self._tools.get(tool_name)
        if tool is None:
            return _registry_error(
                code="unknown_tool",
                message="The requested MemCommit agent tool is not registered.",
            )
        try:
            result = tool.handler(payload)
            if not isinstance(result, Mapping) or not _has_only_text_object_keys(
                result
            ):
                raise TypeError("Agent tool result must be an object with text keys.")
            serialized = json.dumps(
                result,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            decoded = json.loads(serialized)
            if not isinstance(decoded, dict):
                raise TypeError("Agent tool result must decode to an object.")
            return decoded
        except Exception:
            # Registry callers must not receive host paths, provider bodies,
            # or custom handler exceptions through the transport boundary.
            return _registry_error(
                code="internal_error",
                message="The registered MemCommit agent tool failed internally.",
            )


def build_default_agent_tool_registry(client: MemCommitClient) -> AgentToolRegistry:
    """Bind shipped contracts to one public client and application graph."""

    if not isinstance(client, MemCommitClient):
        raise TypeError("Default agent tool registry requires a MemCommitClient.")
    query = QueryAgentAdapter(client)
    add = AddAgentAdapter(client)
    meld = MeldAgentAdapter(client)
    atomize = AtomizeAgentAdapter(client)
    atomize_grounding = AtomizeGroundingAgentAdapter(client)
    distill = DistillAgentAdapter(client)
    elaborate = ElaborateAgentAdapter(client)
    fit = FitAgentAdapter(client)
    return AgentToolRegistry(
        (
            AgentToolBinding(
                name=QUERY_AGENT_TOOL_NAME,
                schema_factory=query_agent_tool_schema,
                handler=query.invoke,
            ),
            AgentToolBinding(
                name=ADD_AGENT_TOOL_NAME,
                schema_factory=add_agent_tool_schema,
                handler=add.invoke,
            ),
            AgentToolBinding(
                name=MELD_AGENT_TOOL_NAME,
                schema_factory=meld_agent_tool_schema,
                handler=meld.invoke,
            ),
            AgentToolBinding(
                name=ATOMIZE_AGENT_TOOL_NAME,
                schema_factory=atomize_agent_tool_schema,
                handler=atomize.invoke,
            ),
            AgentToolBinding(
                name=ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
                schema_factory=atomize_grounding_agent_tool_schema,
                handler=atomize_grounding.invoke,
            ),
            AgentToolBinding(
                name=DISTILL_AGENT_TOOL_NAME,
                schema_factory=distill_agent_tool_schema,
                handler=distill.invoke,
            ),
            AgentToolBinding(
                name=ELABORATE_AGENT_TOOL_NAME,
                schema_factory=elaborate_agent_tool_schema,
                handler=elaborate.invoke,
            ),
            AgentToolBinding(
                name=FIT_AGENT_TOOL_NAME,
                schema_factory=fit_agent_tool_schema,
                handler=fit.invoke,
            ),
        )
    )


__all__ = [
    "AGENT_TOOL_REGISTRY_VERSION",
    "AgentToolBinding",
    "AgentToolHandler",
    "AgentToolRegistrationError",
    "AgentToolRegistry",
    "AgentToolSchemaFactory",
    "build_default_agent_tool_registry",
]
