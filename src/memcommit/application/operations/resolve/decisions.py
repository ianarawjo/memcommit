"""Turn finalized Resolve decisions into one whole-Context Update plan."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from memcommit.application.authorization import ContextUse
from memcommit.application.capabilities.memory_issue_analysis.model import FindingsProvider
from memcommit.application.operations.audit.application import (
    audit_conformance_rules_context,
    run_quality_audit,
)
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.update.application import (
    apply_update,
    materialize_update_post_image,
)
from memcommit.application.operations.update.model import (
    UpdatePlan,
    UpdateProvider,
    UpdateResult,
    plan_update,
)
from memcommit.core.context import Context, Memory

from .application import (
    ResolveAnalysis,
    ResolveError,
    ResolveFramePort,
    ResolveIssue,
    ResolveReceipt,
)
from .semantic import all_audit_issue_keys


ResolveDecisionKind = Literal["CONFIRM", "INTENT", "FORCE"]


@dataclass(frozen=True, slots=True)
class ResolveDecision:
    """One explicit human decision for one frozen Audit direction."""

    issue_uid: str
    kind: ResolveDecisionKind
    intent: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.issue_uid, str) or not self.issue_uid.strip():
            raise ResolveError("A Resolve decision requires an Issue uid.")
        if self.kind not in {"CONFIRM", "INTENT", "FORCE"}:
            raise ResolveError("A Resolve decision kind is invalid.")
        if not isinstance(self.intent, str):
            raise TypeError("Resolve intent must be text.")
        if self.kind == "INTENT" and not self.intent.strip():
            raise ResolveError("PROVIDE YOUR INTENT requires nonblank text.")
        if self.kind != "INTENT" and self.intent:
            raise ResolveError("Only PROVIDE YOUR INTENT may carry response text.")


@dataclass(frozen=True, slots=True)
class ResolveDecisionSet:
    """Complete decisions bound to one frozen Resolve revision."""

    revision: str
    decisions: tuple[ResolveDecision, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision:
            raise ResolveError("Resolve decisions require a frozen revision.")
        if not isinstance(self.decisions, tuple) or any(
            not isinstance(value, ResolveDecision) for value in self.decisions
        ):
            raise TypeError("Resolve decisions must be typed values.")
        if len({decision.issue_uid for decision in self.decisions}) != len(
            self.decisions
        ):
            raise ResolveError("Resolve decisions must name each Issue once.")

    @property
    def forced_issue_uids(self) -> tuple[str, ...]:
        return tuple(
            decision.issue_uid
            for decision in self.decisions
            if decision.kind == "FORCE"
        )


@dataclass(frozen=True, slots=True)
class ResolveFinalizedInput:
    """Exact semantic input retained in the Resolve checkpoint."""

    issue_uid: str
    kind: ResolveDecisionKind
    content: str

    def to_dict(self) -> dict[str, str]:
        return {
            "issue_uid": self.issue_uid,
            "kind": self.kind,
            "content": self.content,
        }


@dataclass(frozen=True, slots=True)
class ResolveUpdateProposal:
    """Detached whole-Context result of one finalized Resolve decision set."""

    analysis: ResolveAnalysis
    decisions: ResolveDecisionSet
    source: Context
    target: Context
    plan: UpdatePlan
    result: UpdateResult
    post_image: Context
    post_audit: QualityAuditSession
    blocking_audit_keys: tuple[str, ...]

    @property
    def unresolved_issue_uids(self) -> tuple[str, ...]:
        remaining = set(all_audit_issue_keys(self.post_audit))
        issue_by_uid = {
            issue.uid: issue for issue in _review_issues(self.analysis)
        }
        return tuple(
            issue_uid
            for issue_uid in self.decisions.forced_issue_uids
            if issue_by_uid[issue_uid].audit_key in remaining
        )

    @property
    def ready_to_apply(self) -> bool:
        return not self.blocking_audit_keys

    @property
    def finalized_inputs(self) -> tuple[ResolveFinalizedInput, ...]:
        issue_by_uid = {
            issue.uid: issue for issue in _review_issues(self.analysis)
        }
        return tuple(
            ResolveFinalizedInput(
                issue_uid=decision.issue_uid,
                kind=decision.kind,
                content=(
                    issue_by_uid[decision.issue_uid].proposed_direction
                    if decision.kind == "CONFIRM"
                    else decision.intent
                    if decision.kind == "INTENT"
                    else ""
                ),
            )
            for decision in self.decisions.decisions
        )


def _review_issues(analysis: ResolveAnalysis) -> tuple[ResolveIssue, ...]:
    issues = analysis.review_issues
    if not issues:
        raise ResolveError(
            "Resolve has no concrete Audit direction to finalize."
        )
    return issues


def finalize_resolve_decisions(
    analysis: ResolveAnalysis,
    decisions: tuple[ResolveDecision, ...],
) -> ResolveDecisionSet:
    """Require exactly one explicit decision for every displayed Issue."""

    if not isinstance(analysis, ResolveAnalysis):
        raise TypeError("Resolve finalization requires a typed analysis.")
    result = ResolveDecisionSet(analysis.frame.revision, decisions)
    expected = tuple(issue.uid for issue in _review_issues(analysis))
    actual = tuple(decision.issue_uid for decision in result.decisions)
    if set(actual) != set(expected) or len(actual) != len(expected):
        missing = tuple(uid for uid in expected if uid not in actual)
        extra = tuple(uid for uid in actual if uid not in expected)
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unknown " + ", ".join(extra))
        raise ResolveError(
            "FINALIZE DECISIONS requires one response per Issue"
            + (": " + "; ".join(detail) if detail else ".")
        )
    by_uid = {decision.issue_uid: decision for decision in result.decisions}
    return ResolveDecisionSet(
        revision=result.revision,
        decisions=tuple(by_uid[uid] for uid in expected),
    )


def _source_identity(decisions: ResolveDecisionSet) -> str:
    payload = {
        "revision": decisions.revision,
        "decisions": [
            {
                "issue_uid": decision.issue_uid,
                "kind": decision.kind,
                "intent": decision.intent,
            }
            for decision in decisions.decisions
            if decision.kind != "FORCE"
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_resolution_source(
    analysis: ResolveAnalysis,
    decisions: ResolveDecisionSet,
) -> Context:
    """Build the process-local Source Context consumed by ordinary Update."""

    if decisions.revision != analysis.frame.revision:
        raise ResolveError("Resolve decisions no longer match this Context revision.")
    issues = {issue.uid: issue for issue in _review_issues(analysis)}
    digest = _source_identity(decisions)
    source = Context(
        uid=str(uuid.uuid5(uuid.NAMESPACE_URL, f"memcommit:resolve:{digest}")),
        name=f"RESOLVE INPUT · {analysis.frame.display_name}",
    )
    for decision in decisions.decisions:
        if decision.kind == "FORCE":
            # FORCE is control/audit state. Treating it as evidence would let
            # an unresolved choice authorize an unrelated target mutation.
            continue
        issue = issues[decision.issue_uid]
        intended = (
            issue.proposed_direction
            if decision.kind == "CONFIRM"
            else decision.intent.strip()
        )
        members = ", ".join(issue.memory_uids)
        content = (
            f"Resolution input for target Context {analysis.frame.display_name!r}.\n"
            f"Audit item {issue.uid!r} is {issue.kind} ({issue.classification})"
            f" and concerns target Memories [{members}].\n"
            f"The accepted direction is: {intended}\n"
            "Update the complete target Context so this meaning is represented "
            "consistently, while preserving unrelated information."
        )
        memory_uid = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"memcommit:resolve:{digest}:{decision.issue_uid}",
            )
        )
        source.add(Memory(uid=memory_uid, content=content))
    return source


def _allowed_target_uses(analysis: ResolveAnalysis) -> frozenset[ContextUse]:
    mapping = {
        "CREATE": ContextUse.CREATE,
        "UPDATE": ContextUse.UPDATE,
        "DELETE": ContextUse.DELETE,
    }
    return frozenset(mapping[value] for value in analysis.frame.allowed_effects)


def _forced_audit_keys(
    analysis: ResolveAnalysis,
    decisions: ResolveDecisionSet,
) -> frozenset[str]:
    issues = {issue.uid: issue for issue in _review_issues(analysis)}
    return frozenset(
        issues[decision.issue_uid].audit_key
        for decision in decisions.decisions
        if decision.kind == "FORCE"
    )


def plan_resolve_update(
    analysis: ResolveAnalysis,
    decisions: tuple[ResolveDecision, ...],
    *,
    frame_port: ResolveFramePort,
    update_provider_factory: Callable[[], UpdateProvider],
    audit_provider_factory: Callable[[], FindingsProvider],
) -> ResolveUpdateProposal:
    """Plan once with Update, then Audit the detached complete post-image."""

    finalized = finalize_resolve_decisions(analysis, decisions)
    if analysis.audit is None:
        raise ResolveError("Resolve Update planning requires its exact Audit.")
    frame_port.revalidate(analysis.frame)
    target = frame_port.load_target(analysis.frame)
    source = build_resolution_source(analysis, finalized)
    if source.memories:
        session = plan_update(
            source,
            target,
            update_provider_factory,
            status="staged",
            granted_target=analysis.frame.granted_binding,
            allowed_target_uses=_allowed_target_uses(analysis),
        )
        plan = session.plan
    else:
        plan = UpdatePlan(
            uid=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"memcommit:resolve-force:{_source_identity(finalized)}",
                )
            ),
            target_uid=target.uid,
            target_name=target.name,
            operations=(),
        )
    result = apply_update(plan, target)
    post_image = materialize_update_post_image(result, target)
    post_audit = run_quality_audit(
        post_image,
        audit_provider_factory,
        conformance_rules=audit_conformance_rules_context(analysis.audit),
    )
    permitted_keys = _forced_audit_keys(analysis, finalized)
    blocking = tuple(
        key
        for key in all_audit_issue_keys(post_audit)
        if key not in permitted_keys
    )
    # The freeze is checked once more after both semantic turns, so a complete
    # proposal is never published from stale target evidence.
    frame_port.revalidate(analysis.frame)
    return ResolveUpdateProposal(
        analysis=analysis,
        decisions=finalized,
        source=source,
        target=target,
        plan=plan,
        result=result,
        post_image=post_image,
        post_audit=post_audit,
        blocking_audit_keys=blocking,
    )


def apply_resolve_update(
    proposal: ResolveUpdateProposal,
    *,
    frame_port: ResolveFramePort,
) -> ResolveReceipt:
    """Publish the exact reviewed Update plan through Resolve authority."""

    if not isinstance(proposal, ResolveUpdateProposal):
        raise TypeError("Resolve Apply requires a typed Update proposal.")
    if proposal.blocking_audit_keys:
        raise ResolveError(
            "The proposed whole Context still contains an unforced Audit issue; "
            "Resolve must collect another decision before Apply."
        )
    return frame_port.apply_update_plan(
        proposal.analysis.frame,
        proposal.plan,
        unresolved_issue_uids=proposal.unresolved_issue_uids,
        finalized_inputs=proposal.finalized_inputs,
    )


__all__ = [
    "ResolveDecision",
    "ResolveDecisionKind",
    "ResolveDecisionSet",
    "ResolveFinalizedInput",
    "ResolveUpdateProposal",
    "apply_resolve_update",
    "build_resolution_source",
    "finalize_resolve_decisions",
    "plan_resolve_update",
]
