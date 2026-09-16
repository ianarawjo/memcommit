"""Import-only compatibility surface; use role, spec, or values internally."""

from memcommit.adapters.console.terminal.components.endpoint_setup.role import (
    EndpointMemoryOptions,
    EndpointNewContextOptions,
    EndpointSetupRole,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.spec import (
    EndpointSetupMode,
    EndpointSetupSpec,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.values import (
    EndpointSetupDraft,
    EndpointSetupMemory,
    EndpointSetupValue,
)

__all__ = [
    "EndpointMemoryOptions",
    "EndpointNewContextOptions",
    "EndpointSetupRole",
    "EndpointSetupMode",
    "EndpointSetupSpec",
    "EndpointSetupDraft",
    "EndpointSetupMemory",
    "EndpointSetupValue",
]
