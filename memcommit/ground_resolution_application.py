"""Source-specific assembly for Ground Resolve plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from memcommit.context import Context
from memcommit.fit_store import GroundFitReceipt
from memcommit.ground import (
    GroundSession,
    propose_ground_example,
    propose_ground_rule,
    review_ground_item,
    revise_ground_goal,
    set_ground_example_use,
)
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
from memcommit.store import MemoryStore


GroundResolutionArtifact: TypeAlias = (
    GroundFitReceipt | GroundDistillResult | GroundElaborateResult
)


@dataclass(frozen=True)
class GroundResolutionApplyReceipt:
    """One exact Resolve outcome; DEFER is successful but non-mutating."""

    plan_digest: str
    artifact_uid: str
    action_kind: str
    previous_identity: GroundResolutionIdentity
    resulting_identity: GroundResolutionIdentity
    mutated: bool


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
        if choice.use not in {"INCLUDE", "EXCLUDE"}:
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


def _revalidate_plan(
    session: GroundSession,
    plan: GroundResolutionPlan,
    artifact: GroundResolutionArtifact,
) -> GroundResolutionPlan:
    """Rebuild a plan from its exact artifact so hand-built plans fail closed."""

    if isinstance(artifact, GroundDistillResult):
        if plan.source.kind != "DISTILL":
            raise GroundResolutionError("Resolve plan and artifact kinds differ.")
        rebuilt = resolve_distill_rule(
            session,
            artifact,
            rule_uid=plan.action.source_item_uid,
        )
    elif isinstance(artifact, GroundElaborateResult):
        if plan.source.kind != "ELABORATE":
            raise GroundResolutionError("Resolve plan and artifact kinds differ.")
        rebuilt = resolve_elaborate_candidate(
            session,
            artifact,
            candidate_uid=plan.action.source_item_uid,
        )
    elif isinstance(artifact, GroundFitReceipt):
        if plan.source.kind != "FIT":
            raise GroundResolutionError("Resolve plan and artifact kinds differ.")
        if plan.action.kind not in {
            "REVISE_GOAL",
            "REFINE_RULE",
            "REFINE_EXAMPLE",
            "SET_EXAMPLE_USE",
            "DEFER",
        }:
            raise GroundResolutionError("Resolve Fit plan has an invalid action.")
        rebuilt = resolve_fit_issue(
            session,
            artifact,
            choice=GroundFitResolutionChoice(
                example_uid=plan.action.source_item_uid,
                action=plan.action.kind,
                content=plan.action.content,
                rationale=plan.action.rationale,
                rule_uid=plan.action.selector,
                use=plan.action.use,
            ),
        )
    else:
        raise TypeError("Resolve application requires a supported source artifact.")
    if rebuilt != plan:
        raise GroundResolutionError(
            "Resolve plan does not exactly match its source artifact."
        )
    return rebuilt


def _load_bound_contexts(
    store: MemoryStore,
    session: GroundSession,
) -> tuple[Context, ...]:
    # Loading happens before the store's save-boundary frame locks; the Ground
    # primitive validates this snapshot and save_ground_session verifies it
    # again under the graph/Context/Ground lock order.
    return tuple(store.load(frame.context_name) for frame in session.frames)


def apply_ground_resolution(
    store: MemoryStore,
    plan: GroundResolutionPlan,
    *,
    artifact: GroundResolutionArtifact,
) -> GroundResolutionApplyReceipt:
    """Apply one revalidated plan through existing revision and store CAS rules."""

    if not isinstance(store, MemoryStore):
        raise TypeError("Resolve application requires a MemoryStore.")
    if not isinstance(plan, GroundResolutionPlan):
        raise TypeError("Resolve application requires a GroundResolutionPlan.")
    previous = store.load_ground_session(plan.source.identity.ground_name)
    if previous is None:
        raise GroundResolutionError("Resolve Ground was not found.")
    _revalidate_plan(previous, plan, artifact)
    action = plan.action
    if action.kind == "DEFER":
        identity = _identity(previous)
        return GroundResolutionApplyReceipt(
            plan_digest=plan.digest,
            artifact_uid=plan.source.artifact_uid,
            action_kind=action.kind,
            previous_identity=identity,
            resulting_identity=identity,
            mutated=False,
        )

    contexts = _load_bound_contexts(store, previous)
    if action.kind == "REVISE_GOAL":
        revised = revise_ground_goal(
            previous,
            action.content,
            reason=action.rationale,
            current_contexts=contexts,
        )
    elif action.kind == "PROPOSE_RULE":
        revised = propose_ground_rule(
            previous,
            rule=action.content,
            rationale=action.rationale,
            current_contexts=contexts,
            rule_provenance=action.rule_provenance,  # type: ignore[arg-type]
        )
    elif action.kind == "PROPOSE_EXAMPLE":
        revised = propose_ground_example(
            previous,
            proposition=action.content,
            rationale=action.rationale,
            current_contexts=contexts,
            case_role=action.case_role,  # type: ignore[arg-type]
            origin="AGENT",
        )
    elif action.kind in {"REFINE_RULE", "REFINE_EXAMPLE"}:
        revised = review_ground_item(
            previous,
            action.selector,
            action="REFINE",
            response=action.content,
            current_contexts=contexts,
        )
    elif action.kind == "SET_EXAMPLE_USE":
        revised = set_ground_example_use(
            previous,
            action.selector,
            use=action.use,
            current_contexts=contexts,
        )
    else:  # pragma: no cover - closed GroundResolutionActionKind
        raise GroundResolutionError("Resolve action is not applicable.")

    store.save_ground_session(
        revised,
        replace=True,
        expected_uid=previous.uid,
        expected_revision=previous.revision,
        expected_digest=ground_session_record_digest(previous),
        verify_bound_frames=True,
    )
    saved = store.load_ground_session(previous.contract_name)
    if saved != revised:
        raise GroundResolutionError("Resolve application could not verify its save.")
    return GroundResolutionApplyReceipt(
        plan_digest=plan.digest,
        artifact_uid=plan.source.artifact_uid,
        action_kind=action.kind,
        previous_identity=_identity(previous),
        resulting_identity=_identity(revised),
        mutated=True,
    )


__all__ = [
    "GroundResolutionApplyReceipt",
    "apply_ground_resolution",
    "resolve_distill_rule",
    "resolve_elaborate_candidate",
    "resolve_fit_issue",
]
