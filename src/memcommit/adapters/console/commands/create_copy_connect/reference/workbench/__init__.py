"""Interactive Reference workbench."""

from memcommit.adapters.console.commands.create_copy_connect.reference.workbench.adapter import (
    build_reference_tui_setup,
    choose_reference_setup,
)
from memcommit.adapters.console.commands.create_copy_connect.reference.workbench.model import (
    ReferenceTuiSetup,
)
from memcommit.adapters.console.commands.create_copy_connect.reference.workbench.screen import (
    context_reference_exact_command_review,
    reference_exact_command_review,
    run_reference_tui,
)

__all__ = [
    "ReferenceTuiSetup",
    "build_reference_tui_setup",
    "choose_reference_setup",
    "context_reference_exact_command_review",
    "reference_exact_command_review",
    "run_reference_tui",
]
