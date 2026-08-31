"""Human-readable receipt for a completed deterministic Replace."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.replace.application import ReplaceApplyResult


def render_replace_apply_result(result: ReplaceApplyResult) -> str:
    if result.applied:
        occurrence = "occurrence" if result.occurrence_count == 1 else "occurrences"
        memory = "Memory" if result.changed_memory_count == 1 else "Memories"
        if len(result.checkpoints) == 1:
            location = (
                " in '" + safe_terminal_text(result.checkpoints[0].context_name) + "'"
            )
        else:
            location = f" across {len(result.checkpoints)} Contexts"
        return "\n".join(
            (
                (
                    f"Replaced {result.occurrence_count} {occurrence} in "
                    f"{result.changed_memory_count} {memory}{location}."
                ),
                "Undo can restore this command.",
            )
        )
    if result.matched_memory_count == 0:
        return "No matches. Nothing changed."
    occurrence = "occurrence" if result.occurrence_count == 1 else "occurrences"
    memory = "Memory" if result.matched_memory_count == 1 else "Memories"
    return (
        f"Found {result.occurrence_count} {occurrence} in "
        f"{result.matched_memory_count} {memory}, but replacement changed no content. "
        "Nothing changed."
    )


__all__ = ["render_replace_apply_result"]
