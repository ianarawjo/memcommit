"""Persistence and Apply boundary for candidate-based Meld resolution."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.meld.model import (
    MELD_CANDIDATE_SCHEMA_VERSION,
    MeldCandidateReview,
    MeldApplication,
    MeldError,
    MeldSession,
    candidate_revision,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.resolution import (
    MeldCandidateProposal,
    MeldTargetEffect,
    advance_meld_candidate_review,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.persistence.store import MemoryStore

from .source_access import (
    assert_meld_non_target_source_bindings,
    assert_unapplied_meld_target,
    load_bound_meld_contexts,
    target_save_source_bindings,
)


@dataclass(frozen=True, slots=True)
class MeldCandidateApplyReceipt:
    session_uid: str
    checkpoint_uid: str | None
    result_count: int
    next_round: int | None
    missing_claim_aliases: tuple[str, ...] = ()

    @property
    def applied(self) -> bool:
        return self.checkpoint_uid is not None


def _apply_effects(target: Context, effects: tuple[MeldTargetEffect, ...]) -> Context:
    result = Context.from_dict(target.to_dict())
    result._store_digest = target._store_digest
    for effect in effects:
        current = result.memories.get(effect.memory_uid)
        if effect.kind == "ADD":
            if current is not None:
                raise MeldError("Meld ADD collided with the current target.")
            result.add(Memory(effect.memory_uid, effect.new_content))
        elif effect.kind == "EDIT":
            if not isinstance(current, Memory) or current.content != effect.old_content:
                raise MeldError("Meld EDIT no longer matches the current target.")
            result.replace(Memory(effect.memory_uid, effect.new_content))
        else:
            if not isinstance(current, Memory) or current.content != effect.old_content:
                raise MeldError("Meld REMOVE no longer matches the current target.")
            result.remove(effect.memory_uid)
    return result


def _decision_record(proposal: MeldCandidateProposal) -> list[dict[str, str]]:
    if proposal.decisions is None:
        return []
    return [
        {
            "issue_uid": decision.issue_uid,
            "kind": decision.kind,
            "intent": decision.intent,
        }
        for decision in proposal.decisions.decisions
    ]


def _checkpoint_record(
    session: MeldSession,
    proposal: MeldCandidateProposal,
) -> dict[str, object]:
    review = session.candidate_review
    assert review is not None
    return {
        "schema_version": MELD_CANDIDATE_SCHEMA_VERSION,
        "contract": "AUDIT_RESOLVE_UPDATE",
        "session_uid": session.uid,
        "change_set_digest": proposal.digest,
        "mode": session.mode,
        "sources": [
            {
                "frame_uid": frame.uid,
                "role": frame.role,
                "context_uid": frame.context_uid,
                "context_name": frame.context_name,
                "context_digest": frame.context_digest,
            }
            for frame in session.frames
        ],
        "target_baseline": session.target.to_dict(),
        "candidate_revision": proposal.expected_revision,
        "audit_uid": review.audit.uid,
        "audit_snapshot_digest": review.audit.snapshot_digest,
        "decisions": _decision_record(proposal),
        "unresolved_audit_keys": list(proposal.forced_audit_keys),
        "update_plan_uid": proposal.update_plan.uid,
        "update_plan_digest": proposal.update_plan.digest,
        "effects": [effect.to_dict() for effect in proposal.target_effects],
        "coverage": [
            {
                "claim_id": item.claim_alias,
                "status": item.status,
                "result_memory_uids": list(item.result_memory_uids),
                "reason": item.reason,
            }
            for item in proposal.coverage.judgments
        ],
        "results": [
            {"memory_uid": item.uid}
            for item in proposal.post_image.iter_items()
            if isinstance(item, Memory)
        ],
    }


def execute_meld_candidate_proposal(
    session: MeldSession,
    proposal: MeldCandidateProposal,
    *,
    store: MemoryStore,
    expected_session_digest: str,
) -> tuple[MeldSession, MeldCandidateApplyReceipt]:
    """Retain a new review round or publish the verified target and receipt."""

    if session.schema_version != MELD_CANDIDATE_SCHEMA_VERSION:
        raise MeldError("Legacy Compare-backed Meld sessions are read-only.")
    if meld_canonical_digest(session.to_dict()) != expected_session_digest:
        raise MeldError("Meld decisions no longer match the reviewed session.")
    review = session.candidate_review
    if (
        review is None
        or proposal.session_uid != session.uid
        or proposal.expected_revision != review.revision
    ):
        raise MeldError("Meld proposal no longer matches its candidate review.")
    if not proposal.coverage.ready:
        return session, MeldCandidateApplyReceipt(
            session_uid=session.uid,
            checkpoint_uid=None,
            result_count=0,
            next_round=None,
            missing_claim_aliases=proposal.coverage.missing_claim_aliases,
        )
    if proposal.blocking_audit_keys:
        if proposal.next_review is None:
            raise MeldError("A blocking Meld post-image has no Resolve review.")
        advance_meld_candidate_review(session, proposal)
        store.save_meld_session(
            session,
            expected_session_digest=expected_session_digest,
        )
        return session, MeldCandidateApplyReceipt(
            session_uid=session.uid,
            checkpoint_uid=None,
            result_count=0,
            next_round=session.candidate_review.round,
        )

    left, right, target = load_bound_meld_contexts(store, session)
    assert_meld_non_target_source_bindings(session, left, right)
    assert_unapplied_meld_target(session, target)
    post_target = _apply_effects(target, proposal.target_effects)
    expected_result = tuple(
        (item.uid, item.content)
        for item in proposal.post_image.iter_items()
        if isinstance(item, Memory)
    )
    actual_result = tuple(
        (item.uid, item.content)
        for item in post_target.iter_items()
        if isinstance(item, Memory)
    )
    if actual_result != expected_result:
        raise MeldError("Meld target projection does not match the verified post-image.")
    result_uids = tuple(uid for uid, _content in actual_result)
    final_round = review.round + 1
    applied = MeldSession.from_dict(session.to_dict())

    def finalize_session(checkpoint):
        applied.candidate_review = MeldCandidateReview(
            round=final_round,
            revision=candidate_revision(
                proposal.post_image,
                review.source_claims,
                round=final_round,
            ),
            candidate=proposal.post_image,
            source_claims=review.source_claims,
            audit=proposal.post_audit,
            issues=(),
            forced_audit_keys=proposal.forced_audit_keys,
        )
        applied.state = "APPLIED"
        applied.application = MeldApplication(
            change_set_digest=proposal.digest,
            checkpoint_uid=checkpoint.uid,
            result_memory_uids=result_uids,
        )
        applied._validate()
        return applied

    checkpoint = store.save_meld_candidate_target_with_session(
        post_target,
        AutoCheckpoint(
            command="meld",
            args={"meld": _checkpoint_record(session, proposal)},
            description=(
                f"Melded '{session.frames[0].context_name}' and "
                f"'{session.frames[1].context_name}' through Audit, Resolve, and Update"
            ),
        ),
        expected_context_digest=session.target.context_digest,
        expected_session_digest=expected_session_digest,
        source_bindings=target_save_source_bindings(store, session),
        finalize_session=finalize_session,
    )
    return applied, MeldCandidateApplyReceipt(
        session_uid=applied.uid,
        checkpoint_uid=checkpoint.uid,
        result_count=len(result_uids),
        next_round=None,
    )


__all__ = [
    "MeldCandidateApplyReceipt",
    "execute_meld_candidate_proposal",
]
