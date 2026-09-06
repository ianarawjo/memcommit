"""History projections shared by read-only and Revert interaction tests."""

from memcommit.adapters.console.terminal.components.history.model import (
    HistoryPickerEntry,
)


def entry(
    suffix: int,
    *,
    description: str = "Added one note",
    uid: str | None = None,
) -> HistoryPickerEntry:
    return HistoryPickerEntry(
        uid=uid or f"00000000-0000-4000-8000-{suffix:012d}",
        timestamp=f"2026-07-30T11:{suffix:02d}:00-04:00",
        command="add",
        description=description,
        detail=(
            f"Snapshot: {suffix + 3} direct items · {suffix} Memories · "
            "1 MemoryRef · 1 query-only Context · 1 embedded Context\n"
            "Transition: +1 added · ~2 edited · -3 removed · 4 reordered"
        ),
    )
