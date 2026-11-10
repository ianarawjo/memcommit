"""Prepare common single-Context ConflictResolution from the verified structural result."""


def prepare_semantic_review(
    prepared, literal_result, *, provider_factory, repository=None
):
    """ConflictResolution one already reconciled Context, without exposing Merge origins."""
    from memcommit.application.operations.audit.model import AuditTarget
    from memcommit.application.operations.conflict.application import (
        CONFLICT_RESOLUTION_CHECKS,
        analyze_conflicts_for_resolution,
    )
    from memcommit.application.operations.conflict.model import (
        ConflictResolutionTarget,
        ConflictResolutionRequest,
    )
    from memcommit.application.operations.conflict.review_round.review_session import (
        ConflictResolutionReviewSession,
    )
    from memcommit.application.operations.conflict.analysis.resolution_options.generate_resolution_directions import (
        ProviderConflictResolutionOptionsPort,
    )

    prepared.require_unchanged()
    review = literal_result.review_input
    if review is None or review.input_digest != prepared.literal_input.digest:
        raise ValueError("Literal result belongs to another Merge input.")
    review.validate_result(literal_result)
    if prepared.request.method != "SEMANTIC":
        raise ValueError("Literal Merge does not run semantic ConflictResolution.")
    source = AuditTarget.from_context(literal_result.post_image)
    request = ConflictResolutionRequest(source.context_name)
    frame = ConflictResolutionTarget(
        request=request,
        display_name=source.context_name,
        source=source,
        revision=literal_result.digest,
        actionable_uids=tuple(item.uid for item in source.items),
    )
    analysis = analyze_conflicts_for_resolution(
        frame,
        checks=CONFLICT_RESOLUTION_CHECKS,
        semantic_port=ProviderConflictResolutionOptionsPort(),
        audit_repository=repository,
        audit_provider_factory=provider_factory,
        direction_provider_factory=provider_factory,
    )
    return ConflictResolutionReviewSession(analysis)
