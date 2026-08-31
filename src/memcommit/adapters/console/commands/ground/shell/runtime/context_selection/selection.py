"""Pure ordering and selection rules for blank-Ground Context candidates."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundShellContextSuggestion,
    GroundShellNewContextSuggestion,
)
from memcommit.adapters.console.commands.ground.shell.runtime.context_selection.model import (
    GroundContextCandidateRow,
)


def ordered_context_rows(
    *,
    fixed_ground_name: str | None,
    suggestions: Sequence[GroundShellContextSuggestion],
    new_suggestions: Sequence[GroundShellNewContextSuggestion],
    current_context_name: str | None,
    discovery_complete: bool,
    direct_context_names: Sequence[str],
) -> tuple[GroundContextCandidateRow, ...]:
    """Return candidates in the same semantic order as their rendered rows."""

    if fixed_ground_name is not None:
        return ()
    current = tuple(
        item for item in suggestions if item.context_name == current_context_name
    )
    main = tuple(
        item
        for item in suggestions
        if item.role == "MAIN" and item.context_name != current_context_name
    )
    alternatives = tuple(
        item
        for item in suggestions
        if item.role == "ALTERNATIVE" and item.context_name != current_context_name
    )
    # A current candidate remains one selectable row rather than appearing
    # twice and making Down move the cursor upward on screen.
    rows = [
        GroundContextCandidateRow(
            kind="EXISTING",
            context_name=item.context_name,
            existing=item,
        )
        for item in (*current, *main, *alternatives)
    ]
    rows.extend(
        GroundContextCandidateRow(
            kind="NEW_SUGGESTION",
            context_name=item.context_name,
        )
        for item in new_suggestions
    )
    if discovery_complete:
        if direct_context_names:
            rows.append(GroundContextCandidateRow(kind="DIRECT_PICK"))
        rows.append(GroundContextCandidateRow(kind="ADD_NEW"))
        if not suggestions:
            rows.append(GroundContextCandidateRow(kind="CONTINUE_EMPTY"))
    return tuple(rows)


def initial_candidate_index(
    rows: Sequence[GroundContextCandidateRow],
) -> int:
    """Prefer the agent's MAIN existing Context when one is present."""

    return next(
        (
            index
            for index, item in enumerate(rows)
            if (
                item.kind == "EXISTING"
                and item.existing is not None
                and item.existing.role == "MAIN"
            )
        ),
        0,
    )


def candidate_row_at(
    rows: Sequence[GroundContextCandidateRow],
    index: int,
) -> tuple[int, GroundContextCandidateRow | None]:
    """Clamp a process-local cursor and return its semantic row."""

    if not rows:
        return 0, None
    clamped = min(max(index, 0), len(rows) - 1)
    return clamped, rows[clamped]


def toggle_selected_context(
    selected_names: Sequence[str],
    context_name: str,
) -> tuple[str, ...]:
    """Toggle one existing name while preserving selection order."""

    selected = list(selected_names)
    if context_name in selected:
        selected.remove(context_name)
    else:
        selected.append(context_name)
    return tuple(selected)
