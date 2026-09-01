"""Lossless Meld candidate and its Audit-backed Resolve review."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from memcommit.application.operations.audit.model import (
    QualityAuditSession,
    QualityAuditSource,
)
from memcommit.application.operations.resolve.application import (
    FrozenResolveFrame,
    ResolveAnalysis,
    ResolveFrameMemory,
    ResolveIssue,
    ResolveRequest,
)
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import context_record_digest

from .source_snapshot import MeldError, MeldFrame, MeldMode, MeldTarget


MELD_CANDIDATE_CONTRACT_VERSION = "meld-candidate-audit-resolve-update"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class MeldSourceClaim:
    """One immutable Source Memory and its identity inside the candidate."""

    alias: str
    frame_uid: str
    context_uid: str
    context_name: str
    memory_uid: str
    candidate_memory_uid: str
    content: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.alias,
                self.frame_uid,
                self.context_uid,
                self.context_name,
                self.memory_uid,
                self.candidate_memory_uid,
                self.content,
            )
        ):
            raise MeldError("A Meld Source claim requires complete values.")

    def to_dict(self) -> dict[str, str]:
        return {
            "alias": self.alias,
            "frame_uid": self.frame_uid,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "memory_uid": self.memory_uid,
            "candidate_memory_uid": self.candidate_memory_uid,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldSourceClaim":
        keys = {
            "alias",
            "frame_uid",
            "context_uid",
            "context_name",
            "memory_uid",
            "candidate_memory_uid",
            "content",
        }
        if not isinstance(value, dict) or set(value) != keys:
            raise MeldError("Invalid Meld Source claim.")
        return cls(**value)  # type: ignore[arg-type]


def _issue_dict(issue: ResolveIssue) -> dict[str, object]:
    return {
        "uid": issue.uid,
        "audit_key": issue.audit_key,
        "audit_snapshot_digest": issue.audit_snapshot_digest,
        "kind": issue.kind,
        "classification": issue.classification,
        "memory_uids": list(issue.memory_uids),
        "proposed_direction": issue.proposed_direction,
        "reason": issue.reason,
        "question": issue.question,
    }


def _issue_from_dict(value: object) -> ResolveIssue:
    keys = {
        "uid",
        "audit_key",
        "audit_snapshot_digest",
        "kind",
        "classification",
        "memory_uids",
        "proposed_direction",
        "reason",
        "question",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise MeldError("Invalid Meld Resolve Issue.")
    memory_uids = value["memory_uids"]
    if not isinstance(memory_uids, list):
        raise MeldError("Invalid Meld Resolve Issue members.")
    return ResolveIssue(
        uid=value["uid"],  # type: ignore[arg-type]
        audit_key=value["audit_key"],  # type: ignore[arg-type]
        audit_snapshot_digest=value["audit_snapshot_digest"],  # type: ignore[arg-type]
        kind=value["kind"],  # type: ignore[arg-type]
        classification=value["classification"],  # type: ignore[arg-type]
        memory_uids=tuple(memory_uids),  # type: ignore[arg-type]
        proposed_direction=value["proposed_direction"],  # type: ignore[arg-type]
        reason=value["reason"],  # type: ignore[arg-type]
        question=value["question"],  # type: ignore[arg-type]
    )


@dataclass(frozen=True, slots=True)
class MeldCandidateReview:
    """One complete candidate post-image awaiting Resolve decisions."""

    round: int
    revision: str
    candidate: Context
    source_claims: tuple[MeldSourceClaim, ...]
    audit: QualityAuditSession
    issues: tuple[ResolveIssue, ...]
    forced_audit_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.round, bool) or self.round < 0:
            raise MeldError("Meld candidate round must be a nonnegative integer.")
        if not isinstance(self.revision, str) or len(self.revision) != 64:
            raise MeldError("Meld candidate revision must be a SHA-256 digest.")
        if not isinstance(self.candidate, Context) or not self.source_claims:
            raise MeldError("Meld candidate review requires Context and Source claims.")
        if len({claim.alias for claim in self.source_claims}) != len(
            self.source_claims
        ):
            raise MeldError("Meld candidate Source aliases must be unique.")
        candidate_uids = {
            item.uid
            for item in self.candidate.iter_items()
            if isinstance(item, Memory)
        }
        if self.round == 0 and not {
            claim.candidate_memory_uid for claim in self.source_claims
        } <= candidate_uids:
            raise MeldError("Meld candidate omitted a frozen Source claim.")
        expected_source = QualityAuditSource.from_context(self.candidate)
        if (
            self.audit.source.context_uid != expected_source.context_uid
            or self.audit.source.context_digest != expected_source.context_digest
        ):
            raise MeldError("Meld candidate Audit does not match its post-image.")
        if any(
            issue.audit_snapshot_digest != self.audit.snapshot_digest
            for issue in self.issues
        ):
            raise MeldError("Meld Resolve directions do not match their Audit.")
        if len({issue.uid for issue in self.issues}) != len(self.issues):
            raise MeldError("Meld Resolve Issue identities must be unique.")
        expected_revision = candidate_revision(
            self.candidate,
            self.source_claims,
            round=self.round,
        )
        if self.revision != expected_revision:
            raise MeldError("Meld candidate revision does not match its evidence.")
        if len(set(self.forced_audit_keys)) != len(self.forced_audit_keys):
            raise MeldError("Meld forced Audit keys must be unique.")

    def to_dict(self) -> dict[str, object]:
        return {
            "round": self.round,
            "revision": self.revision,
            "candidate": self.candidate.to_dict(),
            "source_claims": [claim.to_dict() for claim in self.source_claims],
            "audit": self.audit.to_dict(),
            "issues": [_issue_dict(issue) for issue in self.issues],
            "forced_audit_keys": list(self.forced_audit_keys),
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldCandidateReview":
        keys = {
            "round",
            "revision",
            "candidate",
            "source_claims",
            "audit",
            "issues",
            "forced_audit_keys",
        }
        if not isinstance(value, dict) or set(value) != keys:
            raise MeldError("Invalid Meld candidate review.")
        raw_claims = value["source_claims"]
        raw_issues = value["issues"]
        raw_forced = value["forced_audit_keys"]
        if (
            not isinstance(raw_claims, list)
            or not isinstance(raw_issues, list)
            or not isinstance(raw_forced, list)
        ):
            raise MeldError("Invalid Meld candidate review collections.")
        return cls(
            round=value["round"],  # type: ignore[arg-type]
            revision=value["revision"],  # type: ignore[arg-type]
            candidate=Context.from_dict(value["candidate"]),  # type: ignore[arg-type]
            source_claims=tuple(MeldSourceClaim.from_dict(item) for item in raw_claims),
            audit=QualityAuditSession.from_dict(value["audit"]),
            issues=tuple(_issue_from_dict(item) for item in raw_issues),
            forced_audit_keys=tuple(raw_forced),  # type: ignore[arg-type]
        )

    def resolve_analysis(self) -> ResolveAnalysis:
        """Project the stored review through Resolve's canonical decision model."""

        memories = tuple(
            ResolveFrameMemory(f"m{index}", item.uid, item.content)
            for index, item in enumerate(
                (
                    value
                    for value in self.candidate.iter_items()
                    if isinstance(value, Memory)
                ),
                1,
            )
        )
        frame = FrozenResolveFrame(
            request=ResolveRequest(
                context_name=self.candidate.name,
                allow_create=True,
                allow_delete=True,
                guidance="Integrate every frozen Meld Source claim without silent loss.",
            ),
            context_uid=self.candidate.uid,
            context_name=self.candidate.name,
            display_name=self.candidate.name,
            context_digest=context_record_digest(self.candidate),
            revision=self.revision,
            memories=memories,
            actionable_uids=tuple(memory.uid for memory in memories),
            allowed_effects=("CREATE", "UPDATE", "DELETE"),
        )
        return ResolveAnalysis(
            frame=frame,
            status="NEEDS_INPUT" if self.issues else "NO_ISSUES",
            audit=self.audit,
            question=(
                "Finalize one decision for every Audit item."
                if self.issues
                else "The complete Meld candidate has no Audit issue."
            ),
            issues=self.issues,
        )


def candidate_revision(
    candidate: Context,
    claims: tuple[MeldSourceClaim, ...],
    *,
    round: int,
) -> str:
    return _digest(
        {
            "contract": MELD_CANDIDATE_CONTRACT_VERSION,
            "round": round,
            "candidate": candidate.to_dict(),
            "source_claims": [claim.to_dict() for claim in claims],
        }
    )


def build_lossless_meld_candidate(
    *,
    mode: MeldMode,
    frames: tuple[MeldFrame, MeldFrame],
    target: MeldTarget,
) -> tuple[Context, tuple[MeldSourceClaim, ...]]:
    """Union both frozen frames without semantic inference or information loss."""

    payload = {
        "contract": MELD_CANDIDATE_CONTRACT_VERSION,
        "mode": mode,
        "frames": [frame.context_digest for frame in frames],
        "target": target.to_dict(),
    }
    identity = _digest(payload)
    candidate = Context(
        uid=str(uuid.uuid5(uuid.NAMESPACE_URL, f"memcommit:meld:candidate:{identity}")),
        name=f"MELD CANDIDATE · {target.context_name}",
    )
    # Directional Meld starts from the authoritative BASELINE and adds the
    # INCOMING claims. Symmetric peers retain their displayed A/B order.
    ordered_frames = (frames[1], frames[0]) if mode == "DIRECTIONAL" else frames
    used_uids: set[str] = set()
    claims: list[MeldSourceClaim] = []
    for frame in ordered_frames:
        for memory in frame.memories:
            candidate_uid = memory.uid
            if candidate_uid in used_uids:
                candidate_uid = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"memcommit:meld:claim:{identity}:{frame.uid}:{memory.uid}",
                    )
                )
            used_uids.add(candidate_uid)
            candidate.add(Memory(candidate_uid, memory.content))
            claims.append(
                MeldSourceClaim(
                    alias=f"s{len(claims) + 1}",
                    frame_uid=frame.uid,
                    context_uid=frame.context_uid,
                    context_name=frame.context_name,
                    memory_uid=memory.uid,
                    candidate_memory_uid=candidate_uid,
                    content=memory.content,
                )
            )
    if len(claims) < 2:
        raise MeldError("Meld requires at least two frozen Source Memories.")
    return candidate, tuple(claims)


__all__ = [
    "MELD_CANDIDATE_CONTRACT_VERSION",
    "MeldCandidateReview",
    "MeldSourceClaim",
    "build_lossless_meld_candidate",
    "candidate_revision",
]
