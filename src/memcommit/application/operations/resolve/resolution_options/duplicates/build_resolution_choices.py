"""Offer exact duplicate retention choices without requesting authored intent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from memcommit.application.capabilities.resolution.workbench import ResolutionOption

if TYPE_CHECKING:
    from ...model import ResolveAnalysis, ResolveIssue


def build_resolution_choices(
    analysis: ResolveAnalysis, issue: ResolveIssue
) -> tuple[ResolutionOption, ...]:
    choices = []
    if "DELETE" in analysis.frame.allowed_effects:
        choices.append(("CONFIRM", "KEEP ONE", issue.proposed_direction))
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
