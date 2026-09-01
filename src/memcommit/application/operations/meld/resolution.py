"""Audit→Resolve→Update planning for one lossless Meld candidate."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Callable, Literal

from memcommit.application.authorization import ContextUse
from memcommit.application.capabilities.memory_issue_analysis.model import FindingsProvider
from memcommit.application.operations.audit.application import run_quality_audit
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.audit.repository import AuditRecordRepository
from memcommit.application.operations.meld.coverage import (
    MeldCoverageProvider,
    MeldCoverageReport,
    verify_meld_source_coverage,
)
from memcommit.application.operations.meld.model import (
    MELD_CANDIDATE_SCHEMA_VERSION,
    MeldCandidateReview,
    MeldError,
    MeldSession,
    MeldSourceClaim,
    build_lossless_meld_candidate,
    candidate_revision,
)
from memcommit.application.operations.resolve.application import (
    FrozenResolveFrame,
    ResolveAnalysis,
    ResolveError,
    ResolveFrameMemory,
    ResolveFramePort,
    ResolveRequest,
    run_resolve,
)
from memcommit.application.operations.resolve.decisions import (
    ResolveDecision,
    ResolveDecisionSet,
    build_resolution_source,
    finalize_resolve_decisions,
)
from memcommit.application.operations.resolve.semantic import (
    ProviderResolveSemanticPort,
    all_audit_issue_keys,
)
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
from memcommit.persistence.store import context_record_digest


MeldTargetEffectKind = Literal["ADD", "EDIT", "REMOVE"]


class MeldResolutionError(ValueError):
    """One current Meld decision set cannot advance its reviewed candidate."""


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _copy_context(context: Context) -> Context:
    result = Context.from_dict(context.to_dict())
    result._store_digest = context._store_digest
    return result


@dataclass(frozen=True, slots=True)
class MeldTargetEffect:
    kind: MeldTargetEffectKind
    memory_uid: str
    old_content: str = ""
    new_content: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"ADD", "EDIT", "REMOVE"}:
            raise MeldError("Meld target effect kind is invalid.")
        if not isinstance(self.memory_uid, str) or not self.memory_uid:
            raise MeldError("Meld target effect requires a Memory uid.")
        if self.kind == "ADD" and (self.old_content or not self.new_content):
            raise MeldError("Meld ADD requires only new content.")
        if self.kind == "EDIT" and (
            not self.old_content
            or not self.new_content
            or self.old_content == self.new_content
        ):
            raise MeldError("Meld EDIT requires distinct old and new content.")
        if self.kind == "REMOVE" and (not self.old_content or self.new_content):
            raise MeldError("Meld REMOVE requires only old content.")

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "memory_uid": self.memory_uid,
            "old_content": self.old_content,
            "new_content": self.new_content,
        }


@dataclass(frozen=True, slots=True)
class MeldCandidateProposal:
    """One detached Update result and independent verification evidence."""

    session_uid: str
    expected_revision: str
    decisions: ResolveDecisionSet | None
    update_source: Context
    update_plan: UpdatePlan
    update_result: UpdateResult
    post_image: Context
    post_audit: QualityAuditSession
    coverage: MeldCoverageReport
    target_effects: tuple[MeldTargetEffect, ...]
    forced_audit_keys: tuple[str, ...]
    blocking_audit_keys: tuple[str, ...]
    next_review: MeldCandidateReview | None

    @property
    def ready_to_apply(self) -> bool:
        return self.coverage.ready and not self.blocking_audit_keys

    @property
    def digest(self) -> str:
        return _sha256(
            {
                "session_uid": self.session_uid,
                "expected_revision": self.expected_revision,
                "update_plan_digest": self.update_plan.digest,
                "post_image": self.post_image.to_dict(),
                "target_effects": [effect.to_dict() for effect in self.target_effects],
                "forced_audit_keys": list(self.forced_audit_keys),
                "blocking_audit_keys": list(self.blocking_audit_keys),
                "missing_claims": list(self.coverage.missing_claim_aliases),
            }
        )


class DetachedMeldResolvePort(ResolveFramePort):
    """Expose a process-local candidate to Resolve without mutation authority."""

    def __init__(
        self,
        candidate: Context,
        claims: tuple[MeldSourceClaim, ...],
        *,
        round: int,
    ) -> None:
        self._candidate = _copy_context(candidate)
        self._claims = claims
        self._round = round
        self._revision = candidate_revision(candidate, claims, round=round)

    def freeze(self, request: ResolveRequest) -> FrozenResolveFrame:
        if request.context_name != self._candidate.name:
            raise ResolveError("Meld Resolve request names another candidate.")
        memories = tuple(
            ResolveFrameMemory(f"m{index}", item.uid, item.content)
            for index, item in enumerate(
                (
                    value
                    for value in self._candidate.iter_items()
                    if isinstance(value, Memory)
                ),
                1,
            )
        )
        return FrozenResolveFrame(
            request=request,
            context_uid=self._candidate.uid,
            context_name=self._candidate.name,
            display_name=self._candidate.name,
            context_digest=context_record_digest(self._candidate),
            revision=self._revision,
            memories=memories,
            actionable_uids=tuple(memory.uid for memory in memories),
            allowed_effects=("CREATE", "UPDATE", "DELETE"),
        )

    def revalidate(self, frame: FrozenResolveFrame) -> None:
        if (
            frame.revision != self._revision
            or frame.context_uid != self._candidate.uid
            or frame.context_digest != context_record_digest(self._candidate)
        ):
            raise ResolveError("The detached Meld candidate changed during Resolve.")

    def load_target(self, frame: FrozenResolveFrame) -> Context:
        self.revalidate(frame)
        return _copy_context(self._candidate)

    def apply_update_plan(self, *args, **kwargs):
        raise ResolveError("Meld, not Resolve, owns candidate publication.")


def _resolve_request(candidate: Context) -> ResolveRequest:
    return ResolveRequest(
        context_name=candidate.name,
        allow_create=True,
        allow_delete=True,
        guidance=(
            "Integrate all frozen Meld Source claims into one coherent Context. "
            "Preserve material distinctions and do not silently discard information."
        ),
    )


def analyze_meld_candidate(
    session: MeldSession,
    *,
    audit_repository: AuditRecordRepository,
    provider_factory: Callable[[], FindingsProvider],
) -> MeldSession:
    """Create the lossless candidate, Audit it, and derive Resolve directions."""

    if session.schema_version != MELD_CANDIDATE_SCHEMA_VERSION:
        raise MeldError("Meld candidate analysis requires the current session contract.")
    candidate, claims = build_lossless_meld_candidate(
        mode=session.mode,
        frames=(session.frames[0], session.frames[1]),
        target=session.target,
    )
    port = DetachedMeldResolvePort(candidate, claims, round=0)
    analysis = run_resolve(
        _resolve_request(candidate),
        frame_port=port,
        semantic_port=ProviderResolveSemanticPort(),
        audit_repository=audit_repository,
        audit_provider_factory=provider_factory,
        direction_provider_factory=provider_factory,
    )
    assert analysis.audit is not None
    session.candidate_review = MeldCandidateReview(
        round=0,
        revision=analysis.frame.revision,
        candidate=candidate,
        source_claims=claims,
        audit=analysis.audit,
        issues=analysis.review_issues,
    )
    session.state = "AWAITING_REPLY"
    session._validate()
    return session


def _base_update_source(session: MeldSession, review: MeldCandidateReview) -> Context:
    source = Context(
        uid=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"memcommit:meld:update-input:{review.revision}",
            )
        ),
        name=f"MELD INPUT · {session.target.context_name}",
    )
    route = (
        "Treat BASELINE as the placement target while integrating every INCOMING "
        "claim."
        if session.mode == "DIRECTIONAL"
        else "Create one coherent result from both equal PEER Sources."
    )
    source.add(
        Memory(
            str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"memcommit:meld:update-goal:{review.revision}",
                )
            ),
            (
                f"Meld goal for target {session.target.context_name!r}. {route} "
                "The complete candidate already contains every frozen Source claim. "
                "Rewrite the complete candidate in one Update so compatible material "
                "may be combined, explicit decisions are honored, unrelated details "
                "remain, and no material Source meaning is silently lost."
            ),
        )
    )
    return source


def _build_update_source(
    session: MeldSession,
    analysis: ResolveAnalysis,
    finalized: ResolveDecisionSet | None,
) -> Context:
    source = _base_update_source(session, session.candidate_review)  # type: ignore[arg-type]
    if finalized is None:
        return source
    decisions_source = build_resolution_source(analysis, finalized)
    for memory in decisions_source.iter_items():
        if isinstance(memory, Memory):
            source.add(Memory(memory.uid, memory.content))
    return source


def _target_effects(
    session: MeldSession,
    target: Context,
    post_image: Context,
) -> tuple[MeldTargetEffect, ...]:
    if any(not isinstance(item, Memory) for item in target.iter_items()) or any(
        not isinstance(item, Memory) for item in post_image.iter_items()
    ):
        raise MeldError(
            "Candidate Meld currently materializes direct Memory-only targets."
        )
    before = {
        item.uid: item.content
        for item in target.iter_items()
        if isinstance(item, Memory)
    }
    after = {
        item.uid: item.content
        for item in post_image.iter_items()
        if isinstance(item, Memory)
    }
    effects: list[MeldTargetEffect] = []
    for uid, old_content in before.items():
        new_content = after.get(uid)
        if new_content is None:
            effects.append(MeldTargetEffect("REMOVE", uid, old_content=old_content))
        elif new_content != old_content:
            effects.append(
                MeldTargetEffect(
                    "EDIT",
                    uid,
                    old_content=old_content,
                    new_content=new_content,
                )
            )
    for uid, new_content in after.items():
        if uid not in before:
            effects.append(MeldTargetEffect("ADD", uid, new_content=new_content))
    if session.mode == "SYMMETRIC" and before:
        raise MeldError("A symmetric Meld target must remain empty before Apply.")
    return tuple(effects)


def _next_review(
    review: MeldCandidateReview,
    post_image: Context,
    post_audit,
    *,
    forced_audit_keys: tuple[str, ...],
    direction_provider_factory: Callable[[], FindingsProvider],
) -> MeldCandidateReview | None:
    remaining = tuple(
        key for key in all_audit_issue_keys(post_audit) if key not in forced_audit_keys
    )
    if not remaining:
        return None
    round_number = review.round + 1
    port = DetachedMeldResolvePort(
        post_image,
        review.source_claims,
        round=round_number,
    )
    frame = port.freeze(_resolve_request(post_image))
    semantic = ProviderResolveSemanticPort()
    semantic.preflight(frame, post_audit)
    analysis = semantic.analyze(
        frame,
        post_audit,
        provider=direction_provider_factory(),
    )
    port.revalidate(frame)
    return MeldCandidateReview(
        round=round_number,
        revision=frame.revision,
        candidate=post_image,
        source_claims=review.source_claims,
        audit=post_audit,
        # A forced item remains part of the durable Audit evidence but must not
        # be presented again merely because another new item opened this round.
        issues=tuple(
            issue for issue in analysis.review_issues if issue.audit_key in remaining
        ),
        forced_audit_keys=forced_audit_keys,
    )


def plan_meld_candidate_update(
    session: MeldSession,
    decisions: tuple[ResolveDecision, ...],
    *,
    target: Context,
    update_provider_factory: Callable[[], UpdateProvider],
    audit_provider_factory: Callable[[], FindingsProvider],
    direction_provider_factory: Callable[[], FindingsProvider],
    coverage_provider_factory: Callable[[], MeldCoverageProvider],
) -> MeldCandidateProposal:
    """Run one whole-candidate Update and verify its complete post-image."""

    if session.schema_version != MELD_CANDIDATE_SCHEMA_VERSION:
        raise MeldError("Legacy Compare-backed Meld sessions are read-only.")
    review = session.candidate_review
    if review is None:
        raise MeldError("Meld candidate review is unavailable.")
    analysis = review.resolve_analysis()
    finalized = (
        finalize_resolve_decisions(analysis, decisions)
        if analysis.review_issues
        else None
    )
    if not analysis.review_issues and decisions:
        raise MeldError("A no-Issue Meld candidate does not accept decisions.")
    source = _build_update_source(session, analysis, finalized)
    update_session = plan_update(
        source,
        review.candidate,
        update_provider_factory,
        status="staged",
        allowed_target_uses=frozenset(
            {ContextUse.READ, ContextUse.CREATE, ContextUse.UPDATE, ContextUse.DELETE}
        ),
    )
    result = apply_update(update_session.plan, review.candidate)
    post_image = materialize_update_post_image(result, review.candidate)
    post_audit = run_quality_audit(post_image, audit_provider_factory)
    coverage = verify_meld_source_coverage(
        review.source_claims,
        post_image,
        provider=coverage_provider_factory(),
    )
    newly_forced = tuple(
        issue.audit_key
        for issue in analysis.review_issues
        for decision in (finalized.decisions if finalized is not None else ())
        if decision.issue_uid == issue.uid and decision.kind == "FORCE"
    )
    post_audit_keys = all_audit_issue_keys(post_audit)
    forced_keys = tuple(
        key
        for key in dict.fromkeys((*review.forced_audit_keys, *newly_forced))
        if key in post_audit_keys
    )
    next_review = (
        _next_review(
            review,
            post_image,
            post_audit,
            forced_audit_keys=forced_keys,
            direction_provider_factory=direction_provider_factory,
        )
        if coverage.ready
        else None
    )
    blocking = tuple(
        key for key in post_audit_keys if key not in forced_keys
    )
    return MeldCandidateProposal(
        session_uid=session.uid,
        expected_revision=review.revision,
        decisions=finalized,
        update_source=source,
        update_plan=update_session.plan,
        update_result=result,
        post_image=post_image,
        post_audit=post_audit,
        coverage=coverage,
        target_effects=_target_effects(session, target, post_image),
        forced_audit_keys=forced_keys,
        blocking_audit_keys=blocking,
        next_review=next_review,
    )


def advance_meld_candidate_review(
    session: MeldSession,
    proposal: MeldCandidateProposal,
) -> MeldSession:
    """Retain a new post-image Audit round without publishing target changes."""

    if proposal.session_uid != session.uid or proposal.next_review is None:
        raise MeldError("Meld proposal has no review round to retain.")
    if session.candidate_review is None or (
        session.candidate_review.revision != proposal.expected_revision
    ):
        raise MeldError("Meld candidate changed before its next review.")
    session.candidate_review = proposal.next_review
    session.state = "AWAITING_REPLY"
    session.application = None
    session._validate()
    return session


__all__ = [
    "DetachedMeldResolvePort",
    "MeldCandidateProposal",
    "MeldResolutionError",
    "MeldTargetEffect",
    "advance_meld_candidate_review",
    "analyze_meld_candidate",
    "plan_meld_candidate_update",
]
