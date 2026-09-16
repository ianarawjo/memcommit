"""Shared deterministic Resolution workbench contract and terminal shell."""

from memcommit.adapters.console.terminal.components.resolution.model import (
    ResolutionBulkStrategy,
    ResolutionChoice,
    ResolutionInlineChoice,
    ResolutionItem,
    ResolutionOutcome,
    ResolutionWorkbenchSpec,
)
from memcommit.adapters.console.terminal.components.resolution.shell import (
    run_resolution_workbench,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    run_resolution_workbench_shell,
)

__all__ = [
    "ResolutionChoice",
    "ResolutionInlineChoice",
    "ResolutionBulkStrategy",
    "ResolutionItem",
    "ResolutionOutcome",
    "ResolutionWorkbenchSpec",
    "ResolutionDestination",
    "ResolutionGlobalStrategy",
    "SessionTodoView",
    "run_resolution_workbench",
    "run_resolution_workbench_shell",
]
