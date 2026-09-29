"""Operation-neutral endpoint setup for rebuilt terminal adapters."""

from memcommit.adapters.console.terminal.components.endpoint_setup.role import (
    EndpointMemoryOptions,
    EndpointNewContextOptions,
    EndpointSetupRole,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.screen import (
    run_endpoint_setup_screen,
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
    "EndpointSetupDraft",
    "EndpointSetupMemory",
    "EndpointSetupMode",
    "EndpointSetupRole",
    "EndpointSetupSpec",
    "EndpointSetupValue",
    "run_endpoint_setup_screen",
]
