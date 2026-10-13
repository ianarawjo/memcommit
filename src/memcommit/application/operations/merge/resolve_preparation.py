"""Prepare common single-Context Resolve from the verified structural result."""


def prepare_semantic_review(
    prepared, literal_result, *, provider_factory, repository=None
):
    """Resolve one already reconciled Context, without exposing Merge origins."""
    from memcommit.application.operations.audit.model import AuditTarget
    from memcommit.application.operations.resolve.application import (
        RESOLVE_CHECKS,
        run_resolve,
    )
    from memcommit.application.operations.resolve.model import (
        ResolveTarget,
        ResolveRequest,
    )
    from memcommit.application.operations.resolve.review_round.review_session import (
        ResolveReviewSession,
    )
    from memcommit.application.operations.resolve.analysis.resolution_options.generate_resolution_directions import (
        ProviderResolveOptionsPort,
    )

    prepared.require_unchanged()
    review = literal_result.review_input
    if review is None or review.input_digest != prepared.literal_input.digest:
        raise ValueError("Literal result belongs to another Merge input.")
    review.validate_result(literal_result)
    if prepared.request.method != "SEMANTIC":
        raise ValueError("Literal Merge does not run semantic Resolve.")
    source = AuditTarget.from_context(literal_result.post_image)
    request = ResolveRequest(
        source.context_name,
        allow_create=True,
        allow_delete=True,
        guidance="Retire a Memory only when an explicitly accepted resolution justifies its removal.",
    )
    frame = ResolveTarget(
        request=request,
        display_name=source.context_name,
        source=source,
        revision=literal_result.digest,
        actionable_uids=tuple(item.uid for item in source.items),
        allowed_effects=request.requested_effects,
    )
    analysis = run_resolve(
        frame,
        checks=RESOLVE_CHECKS,
        semantic_port=ProviderResolveOptionsPort(),
        audit_repository=repository,
        audit_provider_factory=provider_factory,
        direction_provider_factory=provider_factory,
    )
    return ResolveReviewSession(analysis)
