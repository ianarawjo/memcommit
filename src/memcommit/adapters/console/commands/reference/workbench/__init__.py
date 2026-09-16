"""Interactive Reference workbench."""

from memcommit.adapters.console.commands.reference.workbench.adapter import (
    build_reference_tui_setup,
    choose_reference_setup,
)
from memcommit.adapters.console.commands.reference.workbench.model import (
    ReferenceTuiSetup,
)
from memcommit.adapters.console.commands.reference.workbench.screen import (
    run_reference_tui,
)

__all__ = [
    "ReferenceTuiSetup",
    "build_reference_tui_setup",
    "choose_reference_setup",
    "run_reference_tui",
]
