"""Operation-neutral endpoint setup for rebuilt terminal adapters."""

from memcommit.adapters.interfaces.tui.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupMemory,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
)
from memcommit.adapters.interfaces.tui.components.endpoint_setup.screen import (
    run_endpoint_setup,
)

__all__ = [
    "EndpointSetupDraft",
    "EndpointSetupMemory",
    "EndpointSetupMode",
    "EndpointSetupRole",
    "EndpointSetupSpec",
    "EndpointSetupValue",
    "run_endpoint_setup",
]
