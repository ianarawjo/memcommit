"""One compact Profile-wide Sync version choice using the shared selector."""

from memcommit.adapters.console.terminal.components.flat_selection_dialog import (
    choose_flat_option,
)
from memcommit.adapters.console.terminal.components.selection import SelectionOption


def choose_sync_conflict_version(_conflicts):
    choice = choose_flat_option(
        (
            SelectionOption("external", "Use external files"),
            SelectionOption("mem", "Use mem"),
        ),
        title="Choose a version for all conflicts in this profile.",
        detail="Both versions will be saved as checkpoints.",
        compact=True,
    )
    return choice.value if choice else None
