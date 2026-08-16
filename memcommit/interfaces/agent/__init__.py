"""Machine-readable adapters over stable MemCommit application facades."""

from memcommit.interfaces.agent.add import (
    ADD_AGENT_CONTRACT_VERSION,
    ADD_AGENT_ERROR_MESSAGE_LIMIT,
    ADD_AGENT_TOOL_NAME,
    AddAgentAdapter,
    add_agent_tool_schema,
)
from memcommit.interfaces.agent.atomize_grounding import (
    ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION,
    ATOMIZE_GROUNDING_AGENT_TOOL_NAME,
    AtomizeGroundingAgentAdapter,
    AtomizeGroundingAgentKind,
    atomize_grounding_agent_tool_schema,
)
from memcommit.interfaces.agent.atomize import (
    ATOMIZE_AGENT_CONTRACT_VERSION,
    ATOMIZE_AGENT_TOOL_NAME,
    AtomizeAgentAdapter,
    AtomizeAgentKind,
    atomize_agent_tool_schema,
)
from memcommit.interfaces.agent.query import (
    QUERY_AGENT_CONTRACT_VERSION,
    QUERY_AGENT_ERROR_MESSAGE_LIMIT,
    QUERY_AGENT_TOOL_NAME,
    QueryAgentAdapter,
    query_agent_tool_schema,
)
from memcommit.interfaces.agent.distill import (
    DISTILL_AGENT_CONTRACT_VERSION,
    DISTILL_AGENT_TOOL_NAME,
    DistillAgentAdapter,
    distill_agent_tool_schema,
)
from memcommit.interfaces.agent.elaborate import (
    ELABORATE_AGENT_CONTRACT_VERSION,
    ELABORATE_AGENT_TOOL_NAME,
    ElaborateAgentAdapter,
    elaborate_agent_tool_schema,
)
from memcommit.interfaces.agent.fit import (
    FIT_AGENT_CONTRACT_VERSION,
    FIT_AGENT_TOOL_NAME,
    FitAgentAdapter,
    fit_agent_tool_schema,
)
from memcommit.interfaces.agent.ground_artifacts import GroundArtifactRegistry
from memcommit.interfaces.agent.ground_resolution import (
    GROUND_RESOLUTION_AGENT_CONTRACT_VERSION,
    GROUND_RESOLUTION_AGENT_TOOL_NAME,
    GroundResolutionAgentAdapter,
    ground_resolution_agent_tool_schema,
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
    "ATOMIZE_AGENT_CONTRACT_VERSION",
    "ATOMIZE_AGENT_TOOL_NAME",
    "ATOMIZE_GROUNDING_AGENT_CONTRACT_VERSION",
    "ATOMIZE_GROUNDING_AGENT_TOOL_NAME",
    "AddAgentAdapter",
    "AgentToolBinding",
    "AgentToolRegistrationError",
    "AgentToolRegistry",
    "AtomizeAgentAdapter",
    "AtomizeAgentKind",
    "AtomizeGroundingAgentAdapter",
    "AtomizeGroundingAgentKind",
    "MELD_AGENT_CONTRACT_VERSION",
    "MELD_AGENT_TOOL_NAME",
    "MeldAgentAdapter",
    "MeldAgentKind",
    "DISTILL_AGENT_CONTRACT_VERSION",
    "DISTILL_AGENT_TOOL_NAME",
    "DistillAgentAdapter",
    "ELABORATE_AGENT_CONTRACT_VERSION",
    "ELABORATE_AGENT_TOOL_NAME",
    "ElaborateAgentAdapter",
    "FIT_AGENT_CONTRACT_VERSION",
    "FIT_AGENT_TOOL_NAME",
    "FitAgentAdapter",
    "GROUND_RESOLUTION_AGENT_CONTRACT_VERSION",
    "GROUND_RESOLUTION_AGENT_TOOL_NAME",
    "GroundArtifactRegistry",
    "GroundResolutionAgentAdapter",
    "QUERY_AGENT_CONTRACT_VERSION",
    "QUERY_AGENT_ERROR_MESSAGE_LIMIT",
    "QUERY_AGENT_TOOL_NAME",
    "QueryAgentAdapter",
    "add_agent_tool_schema",
    "atomize_agent_tool_schema",
    "atomize_grounding_agent_tool_schema",
    "build_default_agent_tool_registry",
    "meld_agent_tool_schema",
    "distill_agent_tool_schema",
    "elaborate_agent_tool_schema",
    "fit_agent_tool_schema",
    "ground_resolution_agent_tool_schema",
    "query_agent_tool_schema",
]
