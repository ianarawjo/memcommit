"""Frozen in-process registry for versioned MemCommit agent tools."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import json
from types import MappingProxyType

from memcommit.api import HelpDetailReferenceResult, MemCommitClient
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
from memcommit.interfaces.agent.compare import (
    COMPARE_AGENT_TOOL_NAME,
    CompareAgentAdapter,
    compare_agent_tool_schema,
)
from memcommit.interfaces.agent.delete import (
    APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME,
    PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME,
    REMOVE_ITEM_AGENT_TOOL_NAME,
    DeleteAgentAdapter,
    apply_context_delete_agent_tool_schema,
    plan_context_delete_agent_tool_schema,
    remove_item_agent_tool_schema,
)
from memcommit.interfaces.agent.contract import JsonObject, error_response
from memcommit.interfaces.agent.distill import (
    DISTILL_AGENT_TOOL_NAME,
    DistillAgentAdapter,
    distill_agent_tool_schema,
)
from memcommit.interfaces.agent.dedup import (
    DEDUP_AGENT_TOOL_NAME,
    DedupAgentAdapter,
    dedup_agent_tool_schema,
)
from memcommit.interfaces.agent.elaborate import (
    ELABORATE_AGENT_TOOL_NAME,
    ElaborateAgentAdapter,
    elaborate_agent_tool_schema,
)
from memcommit.interfaces.agent.embed import (
    EMBED_AGENT_TOOL_NAME,
    EmbedAgentAdapter,
    embed_agent_tool_schema,
)
from memcommit.interfaces.agent.fit import (
    FIT_AGENT_TOOL_NAME,
    FitAgentAdapter,
    fit_agent_tool_schema,
)
from memcommit.interfaces.agent.forget import (
    FORGET_AGENT_TOOL_NAME,
    ForgetAgentAdapter,
    forget_agent_tool_schema,
)
from memcommit.interfaces.agent.help import (
    HELP_AGENT_TOOL_NAME,
    HelpAgentAdapter,
    help_agent_tool_schema,
)
from memcommit.interfaces.agent.show import (
    SHOW_AGENT_TOOL_NAME,
    ShowAgentAdapter,
    show_agent_tool_schema,
)
from memcommit.interfaces.agent.search import (
    SEARCH_AGENT_TOOL_NAME,
    SearchAgentAdapter,
    search_agent_tool_schema,
)
from memcommit.interfaces.agent.find import (
    FIND_AGENT_TOOL_NAME,
    FindAgentAdapter,
    find_agent_tool_schema,
)
from memcommit.interfaces.agent.replace import (
    REPLACE_AGENT_TOOL_NAME,
    ReplaceAgentAdapter,
    replace_agent_tool_schema,
)
from memcommit.interfaces.agent.query import (
    QUERY_AGENT_TOOL_NAME,
    QueryAgentAdapter,
    query_agent_tool_schema,
)
from memcommit.interfaces.agent.reference import (
    REFERENCE_AGENT_TOOL_NAME,
    ReferenceAgentAdapter,
    reference_agent_tool_schema,
)
from memcommit.interfaces.agent.quality_find import (
    QUALITY_FIND_AGENT_TOOL_NAME,
    QualityFindAgentAdapter,
    quality_find_agent_tool_schema,
)
from memcommit.interfaces.agent.resolve import (
    RESOLVE_AGENT_TOOL_NAME,
    ResolveAgentAdapter,
    resolve_agent_tool_schema,
)
from memcommit.interfaces.agent.meld import (
    MELD_AGENT_TOOL_NAME,
    MeldAgentAdapter,
    meld_agent_tool_schema,
)
from memcommit.interfaces.agent.memory_transfer import (
    COPY_MEMORIES_AGENT_TOOL_NAME,
    MOVE_MEMORIES_AGENT_TOOL_NAME,
    MemoryTransferAgentAdapter,
    copy_memories_agent_tool_schema,
    move_memories_agent_tool_schema,
)


AGENT_TOOL_REGISTRY_VERSION = 1
AgentToolSchemaFactory = Callable[[], JsonObject]
AgentToolHandler = Callable[[object], JsonObject]


class AgentToolRegistrationError(ValueError):
    """A host supplied an invalid or duplicate tool binding."""


@dataclass(frozen=True)
class AgentToolEffect:
    """Host-neutral effect hints projected into transport safety metadata."""

    read_only: bool
    destructive: bool
    idempotent: bool
    open_world: bool = False

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (
                self.read_only,
                self.destructive,
                self.idempotent,
                self.open_world,
            )
        ):
            raise AgentToolRegistrationError(
                "Agent tool effect hints must be booleans."
            )
        if self.read_only and self.destructive:
            raise AgentToolRegistrationError(
                "A read-only agent tool cannot also be destructive."
            )


@dataclass(frozen=True)
class AgentToolBinding:
    """One schema factory and decoded-payload handler owned by a host."""

    name: str
    schema_factory: AgentToolSchemaFactory
    handler: AgentToolHandler
    use_when: str | None = None
    help_details: tuple[HelpDetailReferenceResult, ...] = ()
    effect: AgentToolEffect | None = None


@dataclass(frozen=True)
class AgentToolDefinition:
    """One fresh standard tool schema plus host-neutral selection guidance."""

    tool_schema: JsonObject
    use_when: str | None = None
    help_details: tuple[HelpDetailReferenceResult, ...] = ()
    effect: AgentToolEffect | None = None


@dataclass(frozen=True)
class _FrozenAgentTool:
    name: str
    schema_json: str
    use_when: str | None
    help_details: tuple[HelpDetailReferenceResult, ...]
    effect: AgentToolEffect | None
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


def _registration_schema(
    binding: AgentToolBinding,
) -> tuple[
    str,
    str | None,
    tuple[HelpDetailReferenceResult, ...],
    AgentToolEffect | None,
]:
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
    schema_use_when = schema.get("use_when")
    if binding.use_when is not None and schema_use_when not in (
        None,
        binding.use_when,
    ):
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} schema and binding use_when differ."
        )
    use_when = binding.use_when if binding.use_when is not None else schema_use_when
    if use_when is not None and (not isinstance(use_when, str) or not use_when.strip()):
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} use_when must be nonblank text."
        )
    if not isinstance(binding.help_details, tuple) or any(
        not isinstance(item, HelpDetailReferenceResult) for item in binding.help_details
    ):
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} help_details must be a typed tuple."
        )
    if binding.effect is not None and not isinstance(
        binding.effect,
        AgentToolEffect,
    ):
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} effect must be an AgentToolEffect."
        )
    detail_ids = [item.id for item in binding.help_details]
    if len(detail_ids) != len(set(detail_ids)):
        raise AgentToolRegistrationError(
            f"Agent tool {binding.name!r} help detail ids must be unique."
        )
    if schema_use_when is not None:
        # Selection guidance is registry discovery metadata, not a nonstandard
        # field in the function-tool schema passed to strict tool hosts.
        schema = dict(schema)
        del schema["use_when"]
    try:
        # Store a canonical JSON snapshot so discovery cannot mutate the
        # registered schema and later factory changes cannot alter this host.
        return (
            json.dumps(
                schema,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            use_when,
            binding.help_details,
            binding.effect,
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
            schema_json, use_when, help_details, effect = _registration_schema(binding)
            frozen[binding.name] = _FrozenAgentTool(
                name=binding.name,
                schema_json=schema_json,
                use_when=use_when,
                help_details=help_details,
                effect=effect,
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

    def tool_definitions(self) -> tuple[AgentToolDefinition, ...]:
        """Return standard schemas paired with frozen discovery guidance."""

        return tuple(
            AgentToolDefinition(
                tool_schema=json.loads(tool.schema_json),
                use_when=tool.use_when,
                help_details=tool.help_details,
                effect=tool.effect,
            )
            for tool in self._tools.values()
        )

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

    def operation_binding(
        operation_name: str,
        *,
        name: str,
        schema_factory: AgentToolSchemaFactory,
        handler: AgentToolHandler,
        effect: AgentToolEffect | None = None,
    ) -> AgentToolBinding:
        guidance = client.describe_operation(operation_name)
        return AgentToolBinding(
            name=name,
            schema_factory=schema_factory,
            handler=handler,
            use_when=guidance.use_when,
            help_details=guidance.details,
            effect=effect,
        )

    help_adapter = HelpAgentAdapter(client)
    show_adapter = ShowAgentAdapter(client)
    search = SearchAgentAdapter(client)
    find = FindAgentAdapter(client)
    replace = ReplaceAgentAdapter(client)
    delete = DeleteAgentAdapter(client)
    query = QueryAgentAdapter(client)
    quality_find = QualityFindAgentAdapter(client)
    add = AddAgentAdapter(client)
    memory_transfer = MemoryTransferAgentAdapter(client)
    reference = ReferenceAgentAdapter(client)
    embed = EmbedAgentAdapter(client)
    compare = CompareAgentAdapter(client)
    meld = MeldAgentAdapter(client)
    atomize = AtomizeAgentAdapter(client)
    atomize_grounding = AtomizeGroundingAgentAdapter(client)
    distill = DistillAgentAdapter(client)
    elaborate = ElaborateAgentAdapter(client)
    fit = FitAgentAdapter(client)
    forget = ForgetAgentAdapter(client)
    resolve = ResolveAgentAdapter(client)
    dedup = DedupAgentAdapter(client)
    return AgentToolRegistry(
        (
            operation_binding(
                "help",
                name=HELP_AGENT_TOOL_NAME,
                schema_factory=help_agent_tool_schema,
                handler=help_adapter.invoke,
            ),
            operation_binding(
                "show",
                name=SHOW_AGENT_TOOL_NAME,
                schema_factory=show_agent_tool_schema,
                handler=show_adapter.invoke,
            ),
            operation_binding(
                "find",
                name=FIND_AGENT_TOOL_NAME,
                schema_factory=find_agent_tool_schema,
                handler=find.invoke,
            ),
            operation_binding(
                "replace",
                name=REPLACE_AGENT_TOOL_NAME,
                schema_factory=replace_agent_tool_schema,
                handler=replace.invoke,
            ),
            operation_binding(
                "delete",
                name=REMOVE_ITEM_AGENT_TOOL_NAME,
                schema_factory=remove_item_agent_tool_schema,
                handler=delete.remove_item,
                effect=AgentToolEffect(
                    read_only=False,
                    destructive=False,
                    idempotent=False,
                ),
            ),
            operation_binding(
                "delete",
                name=PLAN_CONTEXT_DELETE_AGENT_TOOL_NAME,
                schema_factory=plan_context_delete_agent_tool_schema,
                handler=delete.plan_context,
                effect=AgentToolEffect(
                    read_only=True,
                    destructive=False,
                    idempotent=True,
                ),
            ),
            operation_binding(
                "delete",
                name=APPLY_CONTEXT_DELETE_AGENT_TOOL_NAME,
                schema_factory=apply_context_delete_agent_tool_schema,
                handler=delete.apply_context,
                effect=AgentToolEffect(
                    read_only=False,
                    destructive=True,
                    idempotent=False,
                ),
            ),
            operation_binding(
                "search",
                name=SEARCH_AGENT_TOOL_NAME,
                schema_factory=search_agent_tool_schema,
                handler=search.invoke,
            ),
            operation_binding(
                "query",
                name=QUERY_AGENT_TOOL_NAME,
                schema_factory=query_agent_tool_schema,
                handler=query.invoke,
            ),
            AgentToolBinding(
                name=QUALITY_FIND_AGENT_TOOL_NAME,
                schema_factory=quality_find_agent_tool_schema,
                handler=quality_find.invoke,
                use_when=(
                    "Finding duplicate, ambiguous, or conflicting Memories before "
                    "cleanup or review."
                ),
            ),
            operation_binding(
                "add",
                name=ADD_AGENT_TOOL_NAME,
                schema_factory=add_agent_tool_schema,
                handler=add.invoke,
            ),
            operation_binding(
                "copy",
                name=COPY_MEMORIES_AGENT_TOOL_NAME,
                schema_factory=copy_memories_agent_tool_schema,
                handler=memory_transfer.copy,
                effect=AgentToolEffect(
                    read_only=False,
                    destructive=False,
                    idempotent=False,
                ),
            ),
            operation_binding(
                "move",
                name=MOVE_MEMORIES_AGENT_TOOL_NAME,
                schema_factory=move_memories_agent_tool_schema,
                handler=memory_transfer.move,
                effect=AgentToolEffect(
                    read_only=False,
                    destructive=False,
                    idempotent=False,
                ),
            ),
            operation_binding(
                "reference",
                name=REFERENCE_AGENT_TOOL_NAME,
                schema_factory=reference_agent_tool_schema,
                handler=reference.invoke,
            ),
            operation_binding(
                "embed",
                name=EMBED_AGENT_TOOL_NAME,
                schema_factory=embed_agent_tool_schema,
                handler=embed.invoke,
            ),
            operation_binding(
                "compare",
                name=COMPARE_AGENT_TOOL_NAME,
                schema_factory=compare_agent_tool_schema,
                handler=compare.invoke,
            ),
            operation_binding(
                "meld",
                name=MELD_AGENT_TOOL_NAME,
                schema_factory=meld_agent_tool_schema,
                handler=meld.invoke,
            ),
            operation_binding(
                "atomize",
                name=ATOMIZE_AGENT_TOOL_NAME,
                schema_factory=atomize_agent_tool_schema,
                handler=atomize.invoke,
            ),
            AgentToolBinding(
                name=ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
                schema_factory=atomize_grounding_agent_tool_schema,
                handler=atomize_grounding.invoke,
                use_when=(
                    "Discussing or resolving one saved Atomize issue through "
                    "reviewed conversational turns."
                ),
            ),
            operation_binding(
                "distill",
                name=DISTILL_AGENT_TOOL_NAME,
                schema_factory=distill_agent_tool_schema,
                handler=distill.invoke,
            ),
            operation_binding(
                "elaborate",
                name=ELABORATE_AGENT_TOOL_NAME,
                schema_factory=elaborate_agent_tool_schema,
                handler=elaborate.invoke,
            ),
            operation_binding(
                "fit",
                name=FIT_AGENT_TOOL_NAME,
                schema_factory=fit_agent_tool_schema,
                handler=fit.invoke,
            ),
            operation_binding(
                "forget",
                name=FORGET_AGENT_TOOL_NAME,
                schema_factory=forget_agent_tool_schema,
                handler=forget.invoke,
            ),
            operation_binding(
                "resolve",
                name=RESOLVE_AGENT_TOOL_NAME,
                schema_factory=resolve_agent_tool_schema,
                handler=resolve.invoke,
            ),
            operation_binding(
                "dedun",
                name=DEDUP_AGENT_TOOL_NAME,
                schema_factory=dedup_agent_tool_schema,
                handler=dedup.invoke,
            ),
        )
    )


__all__ = [
    "AGENT_TOOL_REGISTRY_VERSION",
    "AgentToolBinding",
    "AgentToolDefinition",
    "AgentToolEffect",
    "AgentToolHandler",
    "AgentToolRegistrationError",
    "AgentToolRegistry",
    "AgentToolSchemaFactory",
    "build_default_agent_tool_registry",
]
