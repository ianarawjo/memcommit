"""Operation-neutral endpoint setup for rebuilt terminal adapters."""

from memcommit.adapters.console.terminal.components.endpoint_setup.command_binding import (
    EndpointCommandBinding,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupMemory,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.screen import (
    run_endpoint_setup,
)

__all__ = [
    "EndpointSetupDraft",
    "EndpointCommandBinding",
    "EndpointSetupMemory",
    "EndpointSetupMode",
    "EndpointSetupRole",
    "EndpointSetupSpec",
    "EndpointSetupValue",
    "run_endpoint_setup",
]
