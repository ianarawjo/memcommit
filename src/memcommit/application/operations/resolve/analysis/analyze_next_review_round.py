"""Analyze the actual post-Audit Context for the next review round."""

from dataclasses import replace
from memcommit.application.operations.merge.analysis.candidate import digest
from ..application import analyze_resolve_audit
from ..model import ResolveAnalysis
from .resolution_options.generate_resolution_directions import (
    ProviderResolveOptionsPort,
)


def analyze_next_review_round(
    proposal, *, direction_provider_factory
) -> ResolveAnalysis:
    """Use the actual post-Audit and post-image, preserving the original scope."""
    audit = proposal.post_audit
    if audit is None:
        raise ValueError("An exact structural result has no next semantic Audit.")
    previous = proposal.analysis.frame
    actionable = tuple(item.uid for item in audit.source.items)
    frame = replace(
        previous,
        source=audit.source,
        revision=digest(
            {"previous": previous.revision, "audit": audit.snapshot_digest}
        ),
        actionable_uids=actionable,
    )
    analysis = analyze_resolve_audit(
        frame,
        audit,
        semantic_port=ProviderResolveOptionsPort(),
        direction_provider_factory=direction_provider_factory,
        rounds=proposal.rounds,
    )
    if not analysis.issues:
        raise ValueError(
            "The next Audit has no actionable response for its remaining issues."
        )
    return analysis
