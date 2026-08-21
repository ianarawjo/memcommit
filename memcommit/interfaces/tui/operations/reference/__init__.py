"""Interactive Reference adapter."""

from memcommit.interfaces.tui.operations.reference.adapter import (
    build_reference_tui_setup,
    choose_reference_setup,
)
from memcommit.interfaces.tui.operations.reference.model import ReferenceTuiSetup
from memcommit.interfaces.tui.operations.reference.screen import (
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
