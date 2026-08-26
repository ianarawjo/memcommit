"""Terminal adapters for Context Meld setup and saved-session review."""

from memcommit.interfaces.tui.operations.meld.model import (
    MeldEndpointSelection,
    MeldTuiSetup,
)
from memcommit.interfaces.tui.operations.meld.setup import (
    choose_meld_endpoint_setup,
    meld_endpoint_setup_spec,
)
from memcommit.interfaces.tui.operations.meld.screen import (
    MeldShellAction,
    run_meld_shell,
)

__all__ = [
    "MeldEndpointSelection",
    "MeldShellAction",
    "MeldTuiSetup",
    "choose_meld_endpoint_setup",
    "meld_endpoint_setup_spec",
    "run_meld_shell",
]
