"""Grounding assessments, follow-ups, proposals, turns, and decisions."""

from __future__ import annotations

from dataclasses import dataclass

from .bindings import (
    AtomizeGroundingArity,
    AtomizeGroundingDecisionAction,
    AtomizeGroundingEffectKind,
    AtomizeGroundingError,
    AtomizeGroundingProposalNecessity,
    AtomizeGroundingProposalOperation,
    AtomizeGroundingQuestionKind,
    AtomizeGroundingQuestionPriority,
    AtomizeGroundingResolution,
    AtomizeGroundingRevision,
    _DECISION_ACTIONS,
    _EFFECT_KINDS,
    _PROPOSAL_NECESSITIES,
    _PROPOSAL_OPERATIONS,
    _QUESTION_KINDS,
    _QUESTION_PRIORITIES,
    _RESOLUTIONS,
    _REVISIONS,
    _canonical_uuid,
    _digest,
    _exact_dict,
    _identifier,
    _identifiers,
    _integer,
    _list,
    _literal,
    _string,
)


@dataclass(frozen=True)
class AtomizeGroundingDirectOutcome:
    """The current judgment about the issue that opened the conversation."""

    status: AtomizeGroundingResolution
    explanation: str
    proposal_uids: tuple[str, ...] = ()
    question_uids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "explanation": self.explanation,
            "proposal_uids": list(self.proposal_uids),
            "question_uids": list(self.question_uids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingDirectOutcome":
        data = _exact_dict(
            value,
            {"status", "explanation", "proposal_uids", "question_uids"},
            "atomize grounding direct outcome",
        )
        return cls(
            status=_literal(
                data["status"],
                _RESOLUTIONS,
                "atomize grounding direct outcome status",
            ),  # type: ignore[arg-type]
            explanation=_string(
                data["explanation"],
                "atomize grounding direct outcome explanation",
            ),
            proposal_uids=_identifiers(
                data["proposal_uids"],
                "atomize grounding direct proposal uid",
                empty=True,
            ),
            question_uids=_identifiers(
                data["question_uids"],
                "atomize grounding direct question uid",
                empty=True,
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingDownstreamEffect:
    """A consequence for one other unary or pair issue."""

    issue_uid: str
    source_uids: tuple[str, ...]
    effect: AtomizeGroundingEffectKind
    explanation: str
    proposal_uids: tuple[str, ...] = ()
    question_uids: tuple[str, ...] = ()

    @property
    def arity(self) -> AtomizeGroundingArity:
        return "UNARY" if len(self.source_uids) == 1 else "PAIR"

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_uid": self.issue_uid,
            "source_uids": list(self.source_uids),
            "effect": self.effect,
            "explanation": self.explanation,
            "proposal_uids": list(self.proposal_uids),
            "question_uids": list(self.question_uids),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "AtomizeGroundingDownstreamEffect":
        data = _exact_dict(
            value,
            {
                "issue_uid",
                "source_uids",
                "effect",
                "explanation",
                "proposal_uids",
                "question_uids",
            },
            "atomize grounding downstream effect",
        )
        source_uids = _identifiers(
            data["source_uids"],
            "atomize grounding downstream source uid",
            uuids=True,
        )
        if len(source_uids) not in {1, 2}:
            raise AtomizeGroundingError(
                "Atomize grounding downstream effects must preserve unary "
                "or pair issue arity."
            )
        return cls(
            issue_uid=_identifier(
                data["issue_uid"],
                "atomize grounding downstream issue uid",
            ),
            source_uids=source_uids,
            effect=_literal(
                data["effect"],
                _EFFECT_KINDS,
                "atomize grounding downstream effect kind",
            ),  # type: ignore[arg-type]
            explanation=_string(
                data["explanation"],
                "atomize grounding downstream explanation",
            ),
            proposal_uids=_identifiers(
                data["proposal_uids"],
                "atomize grounding downstream proposal uid",
                empty=True,
            ),
            question_uids=_identifiers(
                data["question_uids"],
                "atomize grounding downstream question uid",
                empty=True,
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingFollowUp:
    """One explicit conversational repair or scope-check question."""

    uid: str
    kind: AtomizeGroundingQuestionKind
    priority: AtomizeGroundingQuestionPriority
    text: str
    reason: str
    issue_uids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "kind": self.kind,
            "priority": self.priority,
            "text": self.text,
            "reason": self.reason,
            "issue_uids": list(self.issue_uids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingFollowUp":
        data = _exact_dict(
            value,
            {"uid", "kind", "priority", "text", "reason", "issue_uids"},
            "atomize grounding follow-up",
        )
        return cls(
            uid=_identifier(
                data["uid"],
                "atomize grounding follow-up uid",
            ),
            kind=_literal(
                data["kind"],
                _QUESTION_KINDS,
                "atomize grounding follow-up kind",
            ),  # type: ignore[arg-type]
            priority=_literal(
                data["priority"],
                _QUESTION_PRIORITIES,
                "atomize grounding follow-up priority",
            ),  # type: ignore[arg-type]
            text=_string(
                data["text"],
                "atomize grounding follow-up text",
            ),
            reason=_string(
                data["reason"],
                "atomize grounding follow-up reason",
            ),
            issue_uids=_identifiers(
                data["issue_uids"],
                "atomize grounding follow-up issue uid",
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingProposal:
    """One exact, stale-detectable Memory edit or addition."""

    uid: str
    operation: AtomizeGroundingProposalOperation
    necessity: AtomizeGroundingProposalNecessity
    memory_uid: str
    expected_content_digest: str | None
    content: str
    position: int | None
    reason: str
    issue_uids: tuple[str, ...]
    grounded_by_turn_uids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "operation": self.operation,
            "necessity": self.necessity,
            "memory_uid": self.memory_uid,
            "expected_content_digest": self.expected_content_digest,
            "content": self.content,
            "position": self.position,
            "reason": self.reason,
            "issue_uids": list(self.issue_uids),
            "grounded_by_turn_uids": list(self.grounded_by_turn_uids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingProposal":
        data = _exact_dict(
            value,
            {
                "uid",
                "operation",
                "necessity",
                "memory_uid",
                "expected_content_digest",
                "content",
                "position",
                "reason",
                "issue_uids",
                "grounded_by_turn_uids",
            },
            "atomize grounding proposal",
        )
        operation = _literal(
            data["operation"],
            _PROPOSAL_OPERATIONS,
            "atomize grounding proposal operation",
        )
        expected_digest = data["expected_content_digest"]
        position = _integer(
            data["position"],
            "atomize grounding proposal position",
            nullable=True,
        )
        if operation == "EDIT":
            expected_digest = _digest(
                expected_digest,
                "atomize grounding expected content digest",
            )
            if position is not None:
                raise AtomizeGroundingError(
                    "Atomize grounding EDIT proposals cannot change position."
                )
        else:
            if expected_digest is not None:
                raise AtomizeGroundingError(
                    "Atomize grounding ADD proposals cannot expect old content."
                )
        return cls(
            uid=_identifier(
                data["uid"],
                "atomize grounding proposal uid",
            ),
            operation=operation,  # type: ignore[arg-type]
            necessity=_literal(
                data["necessity"],
                _PROPOSAL_NECESSITIES,
                "atomize grounding proposal necessity",
            ),  # type: ignore[arg-type]
            memory_uid=_canonical_uuid(
                data["memory_uid"],
                "atomize grounding proposal Memory uid",
            ),
            expected_content_digest=expected_digest,
            content=_string(
                data["content"],
                "atomize grounding proposal content",
            ),
            position=position,
            reason=_string(
                data["reason"],
                "atomize grounding proposal reason",
            ),
            issue_uids=_identifiers(
                data["issue_uids"],
                "atomize grounding proposal issue uid",
            ),
            grounded_by_turn_uids=_identifiers(
                data["grounded_by_turn_uids"],
                "atomize grounding proposal turn uid",
                uuids=True,
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingAssessment:
    """One provider judgment over the cumulative conversation and Context."""

    provider_response_digest: str
    active_understanding: tuple[str, ...]
    direct: AtomizeGroundingDirectOutcome
    downstream: tuple[AtomizeGroundingDownstreamEffect, ...] = ()
    follow_ups: tuple[AtomizeGroundingFollowUp, ...] = ()
    proposals: tuple[AtomizeGroundingProposal, ...] = ()
    answered_question_uids: tuple[str, ...] = ()

    @property
    def has_required_follow_up(self) -> bool:
        return any(
            question.priority == "REQUIRED" for question in self.follow_ups
        )

    @property
    def ready_to_apply(self) -> bool:
        """Return whether the current understanding is safe to mutate from."""
        return (
            self.direct.status == "RESOLVED"
            and bool(self.proposals)
            and not self.has_required_follow_up
            and not any(
                effect.effect == "NEEDS_CONFIRMATION"
                for effect in self.downstream
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_response_digest": self.provider_response_digest,
            "active_understanding": list(self.active_understanding),
            "direct": self.direct.to_dict(),
            "downstream": [effect.to_dict() for effect in self.downstream],
            "follow_ups": [question.to_dict() for question in self.follow_ups],
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "answered_question_uids": list(
                self.answered_question_uids
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingAssessment":
        data = _exact_dict(
            value,
            {
                "provider_response_digest",
                "active_understanding",
                "direct",
                "downstream",
                "follow_ups",
                "proposals",
                "answered_question_uids",
            },
            "atomize grounding assessment",
        )
        understanding = tuple(
            _string(
                item,
                "atomize grounding active understanding",
            )
            for item in _list(
                data["active_understanding"],
                "atomize grounding active understanding",
            )
        )
        if len(set(understanding)) != len(understanding):
            raise AtomizeGroundingError(
                "Duplicate atomize grounding active understanding."
            )
        downstream = tuple(
            AtomizeGroundingDownstreamEffect.from_dict(item)
            for item in _list(
                data["downstream"],
                "atomize grounding downstream effects",
            )
        )
        follow_ups = tuple(
            AtomizeGroundingFollowUp.from_dict(item)
            for item in _list(
                data["follow_ups"],
                "atomize grounding follow-ups",
            )
        )
        proposals = tuple(
            AtomizeGroundingProposal.from_dict(item)
            for item in _list(
                data["proposals"],
                "atomize grounding proposals",
            )
        )
        if len({effect.issue_uid for effect in downstream}) != len(downstream):
            raise AtomizeGroundingError(
                "Duplicate atomize grounding downstream issue uid."
            )
        if len({item.uid for item in follow_ups}) != len(follow_ups):
            raise AtomizeGroundingError(
                "Duplicate atomize grounding follow-up uid."
            )
        if len({item.uid for item in proposals}) != len(proposals):
            raise AtomizeGroundingError(
                "Duplicate atomize grounding proposal uid."
            )

        direct = AtomizeGroundingDirectOutcome.from_dict(data["direct"])
        known_proposals = {proposal.uid for proposal in proposals}
        known_questions = {question.uid for question in follow_ups}
        question_by_uid = {
            question.uid: question for question in follow_ups
        }
        references = [
            (
                direct.proposal_uids,
                direct.question_uids,
                "direct outcome",
            ),
            *(
                (
                    effect.proposal_uids,
                    effect.question_uids,
                    f"downstream issue '{effect.issue_uid}'",
                )
                for effect in downstream
            ),
        ]
        for proposal_uids, question_uids, label in references:
            if not set(proposal_uids) <= known_proposals:
                raise AtomizeGroundingError(
                    f"Unknown proposal referenced by {label}."
                )
            if not set(question_uids) <= known_questions:
                raise AtomizeGroundingError(
                    f"Unknown follow-up referenced by {label}."
                )
        for effect in downstream:
            if effect.effect == "REQUIRES_CHANGE" and not effect.proposal_uids:
                raise AtomizeGroundingError(
                    "A required downstream change must name a proposal."
                )
            if effect.effect == "NEEDS_CONFIRMATION" and not any(
                question_by_uid[uid].priority == "REQUIRED"
                for uid in effect.question_uids
            ):
                raise AtomizeGroundingError(
                    "A downstream confirmation dependency requires a "
                    "blocking follow-up."
                )

        return cls(
            provider_response_digest=_digest(
                data["provider_response_digest"],
                "atomize grounding provider response digest",
            ),
            active_understanding=understanding,
            direct=direct,
            downstream=downstream,
            follow_ups=follow_ups,
            proposals=proposals,
            answered_question_uids=_identifiers(
                data["answered_question_uids"],
                "atomize grounding answered question uid",
                empty=True,
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingTurn:
    """One user contribution and its optional cumulative assessment."""

    uid: str
    sequence: int
    revision: AtomizeGroundingRevision
    comment: str
    revises_turn_uids: tuple[str, ...] = ()
    answers_question_uids: tuple[str, ...] = ()
    assessment: AtomizeGroundingAssessment | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "sequence": self.sequence,
            "revision": self.revision,
            "comment": self.comment,
            "revises_turn_uids": list(self.revises_turn_uids),
            "answers_question_uids": list(self.answers_question_uids),
            "assessment": (
                self.assessment.to_dict()
                if self.assessment is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingTurn":
        data = _exact_dict(
            value,
            {
                "uid",
                "sequence",
                "revision",
                "comment",
                "revises_turn_uids",
                "answers_question_uids",
                "assessment",
            },
            "atomize grounding turn",
        )
        raw_assessment = data["assessment"]
        return cls(
            uid=_canonical_uuid(
                data["uid"],
                "atomize grounding turn uid",
            ),
            sequence=_integer(
                data["sequence"],
                "atomize grounding turn sequence",
            ),  # type: ignore[arg-type]
            revision=_literal(
                data["revision"],
                _REVISIONS,
                "atomize grounding revision",
            ),  # type: ignore[arg-type]
            comment=_string(
                data["comment"],
                "atomize grounding user comment",
            ),
            revises_turn_uids=_identifiers(
                data["revises_turn_uids"],
                "atomize grounding revised turn uid",
                empty=True,
                uuids=True,
            ),
            answers_question_uids=_identifiers(
                data["answers_question_uids"],
                "atomize grounding answered question uid",
                empty=True,
            ),
            assessment=(
                None
                if raw_assessment is None
                else AtomizeGroundingAssessment.from_dict(raw_assessment)
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingDecision:
    """One auditable user decision about a proposal from an assessed turn."""

    uid: str
    sequence: int
    proposal_uid: str
    action: AtomizeGroundingDecisionAction
    after_turn_uid: str
    rationale: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "sequence": self.sequence,
            "proposal_uid": self.proposal_uid,
            "action": self.action,
            "after_turn_uid": self.after_turn_uid,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingDecision":
        data = _exact_dict(
            value,
            {
                "uid",
                "sequence",
                "proposal_uid",
                "action",
                "after_turn_uid",
                "rationale",
            },
            "atomize grounding decision",
        )
        return cls(
            uid=_canonical_uuid(
                data["uid"],
                "atomize grounding decision uid",
            ),
            sequence=_integer(
                data["sequence"],
                "atomize grounding decision sequence",
            ),  # type: ignore[arg-type]
            proposal_uid=_identifier(
                data["proposal_uid"],
                "atomize grounding decided proposal uid",
            ),
            action=_literal(
                data["action"],
                _DECISION_ACTIONS,
                "atomize grounding decision action",
            ),  # type: ignore[arg-type]
            after_turn_uid=_canonical_uuid(
                data["after_turn_uid"],
                "atomize grounding decision turn uid",
            ),
            rationale=_string(
                data["rationale"],
                "atomize grounding decision rationale",
                empty=True,
            ),
        )
