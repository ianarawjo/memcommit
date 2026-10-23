"""Validate selected Resolve plans and review changes to the same Memory."""

from __future__ import annotations

from collections.abc import Mapping

from memcommit.application.operations.resolve.review_round.build_change_plans_for_choices import (
    ResolveChoicePlan,
    reviewed_choice_plans,
)
from memcommit.application.operations.resolve.review_round.finalize_review_decisions import (
    ResolveDecision,
    finalize_resolve_decisions,
)
from memcommit.application.operations.resolve.review_round.in_round_change_review.find_conflicting_changes import (
    find_conflicting_changes,
)
from memcommit.application.operations.resolve.model import ResolveAnalysis
from memcommit.models.context import Context

from .screen import run_in_round_change_review


def review_selected_changes(
    analysis: ResolveAnalysis,
    decisions: tuple[ResolveDecision, ...],
    *,
    target: Context,
    reviewed_choices: Mapping[ResolveDecision, ResolveChoicePlan],
    header_label: str,
    **terminal_options,
) -> dict[tuple[str, str], str] | None:
    """Return selected candidates, or None when the person returns to choices."""
    finalized = finalize_resolve_decisions(analysis, decisions)
    plans = reviewed_choice_plans(analysis, finalized, reviewed_choices, target)
    conflicts = find_conflicting_changes(plans)
    if not conflicts:
        return {}
    return run_in_round_change_review(
        analysis,
        conflicts,
        header_label=header_label,
        **terminal_options,
    )
