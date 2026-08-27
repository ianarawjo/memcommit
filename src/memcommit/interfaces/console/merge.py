"""Shared compact text projection for structural Merge conflicts."""

from __future__ import annotations

from memcommit.interfaces.console.text import display_escape_text
from memcommit.application.operations.merge.application import (
    FrozenMergePlan,
    MergeConflict,
    MergeItemSnapshot,
)


def merge_plan_summary_lines(plan: FrozenMergePlan) -> tuple[str, str]:
    """Return the stable two-line classification shared by CLI and TUI."""

    return (
        f"MERGE PLAN · {display_escape_text(plan.source_name)} → "
        f"{display_escape_text(plan.target_name)} · {plan.request.reach.value}",
        f"CLASSIFICATION · NEW {len(plan.additions)} · "
        f"UNCHANGED {len(plan.unchanged)} · CONFLICT {len(plan.conflicts)}",
    )


def merge_conflict_summary_lines(conflict: MergeConflict) -> tuple[str, ...]:
    """Project one deterministic conflict without shortening Memory bodies."""

    def item_lines(role: str, item: MergeItemSnapshot) -> tuple[str, ...]:
        return (
            f"  {role} · {display_escape_text(item.description)}",
            *(
                (f"  {role} CONTENT · {display_escape_text(item.content)}",)
                if item.content is not None
                else ()
            ),
        )

    return (
        f"CONFLICT · {conflict.uid} · {conflict.kind.value} · "
        f"{display_escape_text(conflict.source_name)} → "
        f"{display_escape_text(conflict.target_name)}",
        *item_lines("SOURCE", conflict.source),
        *(
            line
            for target in conflict.targets
            for line in item_lines("TARGET", target)
        ),
        f"  WHY · {display_escape_text(conflict.reason)}",
        "  ALLOWED · "
        + " / ".join(decision.value for decision in conflict.allowed_decisions),
    )


__all__ = ["merge_conflict_summary_lines", "merge_plan_summary_lines"]
