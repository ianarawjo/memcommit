"""One compact Profile-wide Sync version choice using the shared selector."""

from memcommit.adapters.console.terminal.components.flat_selection_dialog import (
    choose_flat_option,
)
from memcommit.adapters.console.terminal.components.selection import SelectionOption


def choose_sync_conflict_version(_conflicts):
    choice = choose_flat_option(
        (
            SelectionOption("external", "Use workspace files"),
            SelectionOption("mem", "Use mem"),
        ),
        title="Choose a version for all conflicts in this profile.",
        inline_notes={
            "external": (
                (
                    "class:report-neutral",
                    "(Overwrite mem with workspace files; create checkpoints)",
                ),
            ),
            "mem": (
                (
                    "class:report-neutral",
                    "(Overwrite workspace files with mem) ",
                ),
                (
                    "class:memcommit.error",
                    "(Warning: memcommit cannot restore overwritten workspace files)",
                ),
            ),
        },
        compact=True,
    )
    return choice.value if choice else None
