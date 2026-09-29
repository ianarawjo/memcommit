"""Conflict resolution options; retain the existing choices until tailored."""

from __future__ import annotations

from typing import TYPE_CHECKING

from memcommit.application.capabilities.resolution.workbench import ResolutionOption

if TYPE_CHECKING:
    from ...model import ResolveAnalysis, ResolveIssue


def build_resolution_choices(
    analysis: ResolveAnalysis, issue: ResolveIssue
) -> tuple[ResolutionOption, ...]:
    choices = []
    if issue.item_kind == "MEMORY" or "DELETE" in analysis.frame.allowed_effects:
        choices.append(("CONFIRM", "ACCEPT THIS DIRECTION", issue.proposed_direction))
    if issue.item_kind == "MEMORY":
        choices.append(
            (
                "INTENT",
                "YOUR INTENT",
                "Enter the direction this should follow.",
            )
        )
    choices.append(
        (
            ("KEEP_BOTH" if len(issue.item_uids) > 1 else "KEEP_AS_IS")
            if issue.item_kind == "MEMORY"
            else "FORCE",
            ("KEEP BOTH" if len(issue.item_uids) > 1 else "KEEP AS IS")
            if issue.item_kind == "MEMORY"
            else "LEAVE UNRESOLVED",
            "Preserve the current texts."
            if issue.item_kind == "MEMORY"
            else "Keep the duplicate placements and record this issue as unresolved.",
        )
    )
    return tuple(
        ResolutionOption(kind, label, description)
        for kind, label, description in choices
    )
