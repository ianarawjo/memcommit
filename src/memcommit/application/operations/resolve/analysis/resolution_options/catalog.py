"""Connect issue kinds to their projection, instructions and choice policies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from memcommit.application.capabilities.resolution.workbench import ResolutionOption
from ...model import ResolveAnalysis, ResolveIssue

if TYPE_CHECKING:
    from ...review_round.finalize_review_decisions import ResolveDecision

from .kinds import (
    conflicts as conflicts_instructions,
    ambiguities as ambiguities_instructions,
)
from .kinds.conflicts import (
    audit_to_resolution_issues as conflicts_issues,
    build_resolution_choices as conflicts_choices,
    build_update_instruction as conflicts_update_instruction,
)
from .kinds.ambiguities import (
    audit_to_resolution_issues as ambiguities_issues,
    build_resolution_choices as ambiguities_choices,
    build_update_instruction as ambiguities_update_instruction,
)
from .kinds.duplicates import (
    audit_to_resolution_issues as duplicates_issues,
    build_resolution_choices as duplicates_choices,
)

AUDIT_PROJECTIONS = {
    "REDUNDANCY": duplicates_issues,
    "AMBIGUITY": ambiguities_issues,
    "CONFLICT": conflicts_issues,
}

SUGGESTION_POLICIES = {
    "AMBIGUITY": ambiguities_instructions,
    "CONFLICT": conflicts_instructions,
}

CHOICE_BUILDERS = {
    "REDUNDANCY": duplicates_choices,
    "AMBIGUITY": ambiguities_choices,
    "CONFLICT": conflicts_choices,
}

UPDATE_INSTRUCTION_BUILDERS = {
    "AMBIGUITY": ambiguities_update_instruction,
    "CONFLICT": conflicts_update_instruction,
}


def build_resolution_options(
    analysis: ResolveAnalysis, issue: ResolveIssue
) -> tuple[ResolutionOption, ...]:
    if issue.kind == "REDUNDANCY":
        return duplicates_choices(analysis, issue)
    if issue.choices:
        return issue.choices
    return CHOICE_BUILDERS[issue.kind](analysis, issue)


def build_update_instruction(
    analysis: ResolveAnalysis, issue: ResolveIssue, decision: ResolveDecision
) -> str:
    return UPDATE_INSTRUCTION_BUILDERS[issue.kind](analysis, issue, decision)
