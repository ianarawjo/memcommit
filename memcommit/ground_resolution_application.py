"""Source-specific assembly for Ground Resolve plans."""

from __future__ import annotations

from memcommit.fit_store import GroundFitReceipt
from memcommit.ground import GroundSession
from memcommit.ground_distill import GroundDistillResult
from memcommit.ground_elaborate import GroundElaborateResult
from memcommit.ground_resolution import (
    GroundFitResolutionChoice,
    GroundResolutionAction,
    GroundResolutionError,
    GroundResolutionIdentity,
    GroundResolutionPlan,
    GroundResolutionSource,
)
from memcommit.store import ground_session_record_digest


def _identity(session: GroundSession) -> GroundResolutionIdentity:
    return GroundResolutionIdentity(
        ground_uid=session.uid,
        ground_name=session.contract_name,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
    )


def _require_current(
    session: GroundSession,
    identity: GroundResolutionIdentity,
) -> None:
    if _identity(session) != identity:
        raise GroundResolutionError(
            "The Ground changed after the Resolve source was frozen."
        )
    if session.status != "OPEN":
        raise GroundResolutionError("Resolve requires an open Ground.")


def _select(items: tuple[object, ...], uid: str, label: str) -> object:
    if not isinstance(uid, str) or not uid.strip():
        raise GroundResolutionError(f"Resolve {label} selector is required.")
    matches = tuple(item for item in items if getattr(item, "uid", None) == uid)
    if len(matches) != 1:
        raise GroundResolutionError(f"Resolve {label} is missing or ambiguous.")
    return matches[0]


def resolve_distill_rule(
    session: GroundSession,
    result: GroundDistillResult,
    *,
    rule_uid: str,
) -> GroundResolutionPlan:
    """Project one cited Distill Rule without accepting or rewriting it."""

    frozen = result.frozen
    identity = GroundResolutionIdentity(
        ground_uid=frozen.ground_uid,
        ground_name=frozen.ground_name,
        ground_revision=frozen.ground_revision,
        ground_digest=frozen.ground_digest,
    )
    _require_current(session, identity)
    analysis = result.distill.analysis
    if analysis.goal != session.goal:
        raise GroundResolutionError("Resolve received an invalid Distill artifact.")
    if frozen.example_frame is not None and analysis.source != frozen.example_frame:
        raise GroundResolutionError(
            "Resolve Distill evidence does not match the frozen Ground Examples."
        )
    rule = _select(analysis.rules, rule_uid, "Distill Rule")
    source = GroundResolutionSource(
        kind="DISTILL",
        artifact_uid=analysis.uid,
        artifact_digest=analysis.digest,
        verification="EVIDENCE_BOUND",
        identity=identity,
    )
    return GroundResolutionPlan(
        source=source,
        action=GroundResolutionAction(
            kind="PROPOSE_RULE",
            content=getattr(rule, "content"),
            rationale=getattr(rule, "rationale"),
            source_item_uid=getattr(rule, "uid"),
            rule_provenance="INDUCED_FROM_CASES",
        ),
        explanation=(
            "Project the selected evidence-bound Distill Rule as one still-"
            "unapproved Ground Rule proposal."
        ),
        candidate_verification="EVIDENCE_BOUND",
    )


def resolve_elaborate_candidate(
    session: GroundSession,
    result: GroundElaborateResult,
    *,
    candidate_uid: str,
) -> GroundResolutionPlan:
    """Project one Elaborate suggestion while retaining UNVERIFIED status."""

    frozen = result.frozen
    identity = GroundResolutionIdentity(
        ground_uid=frozen.ground_uid,
        ground_name=frozen.ground_name,
        ground_revision=frozen.ground_revision,
        ground_digest=frozen.ground_digest,
    )
    _require_current(session, identity)
    analysis = result.elaborate.analysis
    candidates = (*analysis.rules, *analysis.cases)
    candidate = _select(candidates, candidate_uid, "Elaborate candidate")
    source = GroundResolutionSource(
        kind="ELABORATE",
        artifact_uid=analysis.uid,
        artifact_digest=analysis.digest,
        verification="UNVERIFIED",
        identity=identity,
    )
    if candidate in analysis.rules:
        action = GroundResolutionAction(
            kind="PROPOSE_RULE",
            content=getattr(candidate, "content"),
            rationale=getattr(candidate, "rationale"),
            source_item_uid=getattr(candidate, "uid"),
            rule_provenance="DISTILLED_FROM_GOAL",
        )
    else:
        action = GroundResolutionAction(
            kind="PROPOSE_EXAMPLE",
            content=getattr(candidate, "proposition"),
            rationale=getattr(candidate, "rationale"),
            source_item_uid=getattr(candidate, "uid"),
            case_role=getattr(candidate, "case_role"),
            expected=getattr(candidate, "expected"),
        )
    return GroundResolutionPlan(
        source=source,
        action=action,
        explanation=(
            "Project the selected Elaborate suggestion as one unverified, "
            "unapproved Ground proposal."
        ),
        candidate_verification="UNVERIFIED",
    )


def resolve_fit_issue(
    session: GroundSession,
    receipt: GroundFitReceipt,
    *,
    choice: GroundFitResolutionChoice,
) -> GroundResolutionPlan:
    """Plan one reviewed response to a non-FIT row of a current receipt."""

    report = receipt.report
    identity = GroundResolutionIdentity(
        ground_uid=report.ground_uid,
        ground_name=report.ground_name,
        ground_revision=report.ground_revision,
        ground_digest=report.ground_digest,
    )
    if not receipt.current:
        raise GroundResolutionError("Resolve cannot use a stale Fit receipt.")
    _require_current(session, identity)
    judgments = tuple(
        judgment
        for judgment in report.judgments
        if judgment.example_uid == choice.example_uid
    )
    if len(judgments) != 1:
        raise GroundResolutionError("Resolve Fit Example is missing or ambiguous.")
    judgment = judgments[0]
    if judgment.status == "FIT":
        raise GroundResolutionError("Resolve requires a non-FIT judgment.")
    ground_examples = tuple(
        item
        for item in session.items
        if item.kind == "CASE" and item.uid == choice.example_uid
    )
    if len(ground_examples) != 1:
        raise GroundResolutionError("Resolve Fit Example is not in the Ground.")
    action = _fit_action(choice, judgment.rule_uids)
    source = GroundResolutionSource(
        kind="FIT",
        artifact_uid=report.uid,
        artifact_digest=report.digest,
        verification="REVISION_BOUND_JUDGMENT",
        identity=identity,
    )
    return GroundResolutionPlan(
        source=source,
        action=action,
        explanation=(
            f"Respond to {judgment.status} for the selected Example without "
            "changing the immutable Fit receipt."
        ),
        candidate_verification=(
            "REVISION_BOUND_JUDGMENT"
            if action.kind in {"SET_EXAMPLE_USE", "DEFER"}
            else "UNVERIFIED"
        ),
    )


def _fit_action(
    choice: GroundFitResolutionChoice,
    judgment_rule_uids: tuple[str, ...],
) -> GroundResolutionAction:
    rationale = choice.rationale.strip()
    content = choice.content.strip()
    if choice.action == "DEFER":
        if content or choice.rule_uid or choice.use:
            raise GroundResolutionError("A deferred Fit issue cannot carry an edit.")
        return GroundResolutionAction(
            kind="DEFER",
            rationale=rationale or "Leave this Fit issue explicitly unresolved.",
            source_item_uid=choice.example_uid,
        )
    if not rationale:
        raise GroundResolutionError("A mutating Resolve action requires a rationale.")
    if choice.action == "REVISE_GOAL":
        if not content:
            raise GroundResolutionError("A Goal revision requires replacement text.")
        return GroundResolutionAction(
            kind="REVISE_GOAL",
            content=content,
            rationale=rationale,
            source_item_uid=choice.example_uid,
        )
    if choice.action == "REFINE_RULE":
        if choice.rule_uid not in judgment_rule_uids or not content:
            raise GroundResolutionError(
                "A Rule refinement must name one cited Rule and replacement text."
            )
        return GroundResolutionAction(
            kind="REFINE_RULE",
            selector=choice.rule_uid,
            content=content,
            rationale=rationale,
            source_item_uid=choice.example_uid,
        )
    if choice.action == "REFINE_EXAMPLE":
        if not content:
            raise GroundResolutionError(
                "An Example refinement requires replacement proposition text."
            )
        return GroundResolutionAction(
            kind="REFINE_EXAMPLE",
            selector=choice.example_uid,
            content=content,
            rationale=rationale,
            source_item_uid=choice.example_uid,
        )
    if choice.action == "SET_EXAMPLE_USE":
        if choice.use not in {"INCLUDE", "EXCLUDE", "UNRESOLVED"}:
            raise GroundResolutionError("Resolve Example USE is invalid.")
        if content or choice.rule_uid:
            raise GroundResolutionError("A USE change cannot carry replacement text.")
        return GroundResolutionAction(
            kind="SET_EXAMPLE_USE",
            selector=choice.example_uid,
            rationale=rationale,
            source_item_uid=choice.example_uid,
            use=choice.use,
        )
    raise GroundResolutionError("Resolve Fit action is invalid.")


__all__ = [
    "resolve_distill_rule",
    "resolve_elaborate_candidate",
    "resolve_fit_issue",
]
