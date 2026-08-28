"""Bounded Meld assessment and repair provider calls."""

from __future__ import annotations

from dataclasses import replace

from memcommit.application.operations.meld.model import (
    MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION,
    MeldAssessment,
    MeldSession,
    directional_comparison_basis_assessment,
)
from memcommit.application.capabilities.semantic_execution import (
    ExecutionMode,
    json_budget,
    plan_semantic_execution,
)

from .contract import (
    MELD_EXECUTION_POLICY,
    MeldProvider,
    MeldProviderError,
    meld_output_schema,
)
from .decoder import _expand_directional_comparison_response, _parse_assessment
from .projection import _assessment_provider_payload, _provider_view
from .request import _meld_turn_request, _prompt


def assess_meld_turn(
    session: MeldSession,
    provider: MeldProvider,
) -> MeldAssessment:
    """Run exactly one bounded semantic call for the current pending turn."""
    request = _meld_turn_request(session)
    response = provider.complete(
        request.prompt,
        operation="meld_contexts",
        output_schema=request.output_schema,
    )
    if request.directional_comparison:
        response = _expand_directional_comparison_response(
            response,
            view=request.view,
        )
    assessment = _parse_assessment(
        response,
        session=session,
        view=request.view,
    )
    if request.directional_comparison:
        # The wire format separates relation members into left/right alias
        # arrays and separates paired/one-sided records. Decoding therefore
        # canonicalizes side grouping and can lose the typed basis's original
        # cross-side member interleaving (as well as relation presentation
        # order). The reviewed Compare objects remain the authority.
        basis = directional_comparison_basis_assessment(
            session.comparison_seed.analysis,
            (session.frames[0], session.frames[1]),
        )
        imported_issue_uids = {issue.uid for issue in basis.issues}
        assessment = replace(
            assessment,
            relations=basis.relations,
            issues=(
                *basis.issues,
                *(
                    issue
                    for issue in assessment.issues
                    if issue.uid not in imported_issue_uids
                ),
            ),
        )
    return assessment


def repair_meld_assessment(
    session: MeldSession,
    rejected: MeldAssessment,
    validation_error: str,
    provider: MeldProvider,
) -> MeldAssessment:
    """Request one bounded repair of a decoded but session-invalid assessment."""
    if not isinstance(session, MeldSession):
        raise MeldProviderError("Expected a MeldSession.")
    if not isinstance(rejected, MeldAssessment):
        raise MeldProviderError("Expected a rejected MeldAssessment.")
    if not isinstance(validation_error, str) or not validation_error.strip():
        raise MeldProviderError("Expected one local Meld validation error.")

    base_view = _provider_view(session)
    (
        rejected_payload,
        rejected_relations,
        rejected_issues,
        rejected_proposals,
    ) = _assessment_provider_payload(session, rejected, base_view)
    repair_payload = {
        **base_view.payload,
        "rejected_assessment": rejected_payload,
        "validation_error": validation_error,
    }
    # Reusing the rejected aliases preserves stable local identities when the
    # provider repairs a record in place. Prior relation carry-forward remains
    # disabled: a repair must return a complete assessment for atomic review.
    view = replace(
        base_view,
        prior_relation_by_id=rejected_relations,
        prior_relation_records={},
        prior_issue_by_id=rejected_issues,
        prior_proposal_by_id=rejected_proposals,
        payload=repair_payload,
    )
    source_count = len(view.memory_by_id)
    source_memory_ids = tuple(view.memory_by_id)
    left_count = len(session.frames[0].memories)
    right_count = len(session.frames[1].memories)
    schema = meld_output_schema(
        source_memory_ids,
        mode=session.mode,
        target_context_count=len(view.target_context_by_id) or 1,
    )
    plan = plan_semantic_execution(
        MELD_EXECUTION_POLICY,
        json_budget(
            view.payload,
            item_count=source_count,
            output_schema=schema,
            expected_output_items=source_count,
            relation_edges=left_count * right_count,
        ),
    )
    if plan.mode is not ExecutionMode.ONE_SHOT:
        axes = ", ".join(plan.exceeded_axes)
        raise MeldProviderError(
            "This rejected Meld assessment exceeds the bounded repair plan "
            f"({axes}). It was not truncated or partially repaired."
        )
    response = provider.complete(
        _prompt(
            view.payload,
            directional_preservation=(
                session.mode == "DIRECTIONAL"
                and session.schema_version
                >= MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION
            ),
            repair=True,
        ),
        operation="meld_contexts_repair",
        output_schema=schema,
    )
    repaired = _parse_assessment(response, session=session, view=view)
    if (
        repaired.overview != rejected.overview
        or tuple(relation.to_dict() for relation in repaired.relations)
        != tuple(relation.to_dict() for relation in rejected.relations)
        or tuple(issue.to_dict() for issue in repaired.issues)
        != tuple(issue.to_dict() for issue in rejected.issues)
        or repaired.ready_to_apply != rejected.ready_to_apply
    ):
        raise MeldProviderError(
            "Codex meld repair changed the frozen semantic analysis."
        )
    return repaired
