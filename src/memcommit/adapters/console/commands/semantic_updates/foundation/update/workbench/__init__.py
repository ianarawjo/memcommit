"""Update-owned composition over the shared Endpoint Setup component."""

from memcommit.adapters.console.commands.semantic_updates.foundation.update.workbench.model import (
    UpdateEndpointSelection,
    UpdateEndpointSetup,
)
from memcommit.adapters.console.commands.semantic_updates.foundation.update.workbench.setup import (
    choose_update_endpoint_setup,
    update_endpoint_setup_spec,
)

__all__ = [
    "UpdateEndpointSelection",
    "UpdateEndpointSetup",
    "choose_update_endpoint_setup",
    "update_endpoint_setup_spec",
]
