"""Update terminal adapter built on shared Endpoint Setup."""

from memcommit.adapters.interfaces.tui.operations.update.model import (
    UpdateEndpointSelection,
    UpdateTuiSetup,
)
from memcommit.adapters.interfaces.tui.operations.update.setup import (
    choose_update_endpoint_setup,
    update_endpoint_setup_spec,
)

__all__ = [
    "UpdateEndpointSelection",
    "UpdateTuiSetup",
    "choose_update_endpoint_setup",
    "update_endpoint_setup_spec",
]
