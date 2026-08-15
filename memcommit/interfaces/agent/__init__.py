"""Machine-readable adapters over stable MemCommit application facades."""

from memcommit.interfaces.agent.add import (
    ADD_AGENT_CONTRACT_VERSION,
    ADD_AGENT_ERROR_MESSAGE_LIMIT,
    ADD_AGENT_TOOL_NAME,
    AddAgentAdapter,
    add_agent_tool_schema,
)
from memcommit.interfaces.agent.query import (
    QUERY_AGENT_CONTRACT_VERSION,
    QUERY_AGENT_ERROR_MESSAGE_LIMIT,
    QUERY_AGENT_TOOL_NAME,
    QueryAgentAdapter,
    query_agent_tool_schema,
)
from memcommit.interfaces.agent.registry import (
    AGENT_TOOL_REGISTRY_VERSION,
    AgentToolBinding,
    AgentToolRegistrationError,
    AgentToolRegistry,
    build_default_agent_tool_registry,
)
from memcommit.interfaces.agent.meld import (
    MELD_AGENT_CONTRACT_VERSION,
    MELD_AGENT_TOOL_NAME,
    MeldAgentAdapter,
    MeldAgentKind,
    meld_agent_tool_schema,
)

__all__ = [
    "ADD_AGENT_CONTRACT_VERSION",
    "ADD_AGENT_ERROR_MESSAGE_LIMIT",
    "ADD_AGENT_TOOL_NAME",
    "AGENT_TOOL_REGISTRY_VERSION",
    "AddAgentAdapter",
    "AgentToolBinding",
    "AgentToolRegistrationError",
    "AgentToolRegistry",
    "MELD_AGENT_CONTRACT_VERSION",
    "MELD_AGENT_TOOL_NAME",
    "MeldAgentAdapter",
    "MeldAgentKind",
    "QUERY_AGENT_CONTRACT_VERSION",
    "QUERY_AGENT_ERROR_MESSAGE_LIMIT",
    "QUERY_AGENT_TOOL_NAME",
    "QueryAgentAdapter",
    "add_agent_tool_schema",
    "build_default_agent_tool_registry",
    "meld_agent_tool_schema",
    "query_agent_tool_schema",
]
