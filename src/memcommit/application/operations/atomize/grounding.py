"""Operation-owned non-mutating state for conversational Atomize grounding.

The records in this module preserve a multi-turn conversation in which a
user's comment can clarify the selected atomize issue, expose consequences
for other issues, prompt a follow-up question, and eventually produce exact
Memory edits or additions for explicit approval.

This module deliberately does not mutate a Context.  ``prepare_changes``
returns a content-addressed plan containing only explicitly accepted current
proposals.  A command-layer transaction must still verify the bound digests,
apply the plan, save the Context, create one checkpoint, and only then record
the application result.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, replace
from typing import Iterable, Literal

from memcommit.context import Context
from memcommit.application.operations.meld.model import (
    MeldError,
    MeldProposalOperation as AtomizeGroundingProposalOperation,
    MeldRevision as AtomizeGroundingRevision,
    validate_meld_turn_lineage,
)


ATOMIZE_GROUNDING_SCHEMA_VERSION = 2
ATOMIZE_GROUNDING_LEGACY_SCHEMA_VERSION = 1
ATOMIZE_GROUNDING_TEXT_LIMIT = 20_000
ATOMIZE_GROUNDING_NAME_LIMIT = 500
ATOMIZE_GROUNDING_ID_LIMIT = 240

AtomizeGroundingArity = Literal["UNARY", "PAIR"]
AtomizeGroundingIssueKind = Literal[
    "AMBIGUITY",
    "CONFLICT",
    "ATOMIZE_SPLIT",
    "ATOMIZE_UNCERTAINTY",
]
AtomizeGroundingState = Literal[
    "AWAITING_REPLY",
    "READY_TO_APPLY",
    "KEPT_REVIEW_ONLY",
    "APPLIED",
]
AtomizeGroundingResolution = Literal[
    "RESOLVED",
    "PARTIAL",
    "UNRESOLVED",
]
AtomizeGroundingEffectKind = Literal[
    "RESOLVES",
    "PARTIALLY_RESOLVES",
    "REQUIRES_CHANGE",
    "NEEDS_CONFIRMATION",
    "UNCHANGED",
]
AtomizeGroundingQuestionKind = Literal[
    "REQUIRED_CHANGE",
    "CLARIFICATION",
    "SCOPE_CHECK",
    "CONSISTENCY_CHECK",
]
AtomizeGroundingQuestionPriority = Literal["REQUIRED", "HELPFUL"]
AtomizeGroundingProposalNecessity = Literal["REQUIRED", "OPTIONAL"]
AtomizeGroundingDecisionAction = Literal["ACCEPT", "REJECT", "DEFER"]

_ARITIES = {"UNARY", "PAIR"}
_ISSUE_KINDS = {
    "AMBIGUITY",
    "CONFLICT",
    "ATOMIZE_SPLIT",
    "ATOMIZE_UNCERTAINTY",
}
_STATES = {
    "AWAITING_REPLY",
    "READY_TO_APPLY",
    "KEPT_REVIEW_ONLY",
    "APPLIED",
}
_REVISIONS = {"INITIAL", "CONFIRM", "EXTEND", "CORRECT", "RETRACT"}
_RESOLUTIONS = {"RESOLVED", "PARTIAL", "UNRESOLVED"}
_EFFECT_KINDS = {
    "RESOLVES",
    "PARTIALLY_RESOLVES",
    "REQUIRES_CHANGE",
    "NEEDS_CONFIRMATION",
    "UNCHANGED",
}
_QUESTION_KINDS = {
    "REQUIRED_CHANGE",
    "CLARIFICATION",
    "SCOPE_CHECK",
    "CONSISTENCY_CHECK",
}
_QUESTION_PRIORITIES = {"REQUIRED", "HELPFUL"}
_PROPOSAL_OPERATIONS = {"EDIT", "ADD"}
_PROPOSAL_NECESSITIES = {"REQUIRED", "OPTIONAL"}
_DECISION_ACTIONS = {"ACCEPT", "REJECT", "DEFER"}


class AtomizeGroundingError(ValueError):
    """Invalid, stale, or internally inconsistent grounding state."""


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = ATOMIZE_GROUNDING_TEXT_LIMIT,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
    ):
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _identifier(value: object, label: str) -> str:
    return _string(value, label, limit=ATOMIZE_GROUNDING_ID_LIMIT)


def _canonical_uuid(value: object, label: str) -> str:
    text = _string(value, label, limit=36)
    try:
        canonical = str(uuid.UUID(text))
    except ValueError as error:
        raise AtomizeGroundingError(f"Invalid {label}.") from error
    if text != canonical:
        raise AtomizeGroundingError(f"Invalid {label}.")
    return text


def _digest(value: object, label: str) -> str:
    text = _string(value, label, limit=64)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise AtomizeGroundingError(f"Invalid {label}.")
    return text


def _integer(
    value: object,
    label: str,
    *,
    nullable: bool = False,
) -> int | None:
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _literal(
    value: object,
    allowed: set[str],
    label: str,
) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise AtomizeGroundingError(f"Invalid {label}.")
    return value


def _identifiers(
    value: object,
    label: str,
    *,
    empty: bool = False,
    uuids: bool = False,
) -> tuple[str, ...]:
    values = _list(value, label)
    if not empty and not values:
        raise AtomizeGroundingError(f"Invalid {label}.")
    parser = _canonical_uuid if uuids else _identifier
    parsed = tuple(parser(item, label) for item in values)
    if len(set(parsed)) != len(parsed):
        raise AtomizeGroundingError(f"Duplicate {label}.")
    return parsed


def atomize_grounding_canonical_digest(value: object) -> str:
    """Return the stable SHA-256 digest used for external snapshot bindings."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomize_grounding_context_digest(ctx: Context) -> str:
    """Bind the complete ordered direct Context, including reference slots.

    The semantic turn reads only directly owned Memories, but ADD proposals
    use positions in the Context's complete direct order.  Binding only those
    Memories would let a concurrent reference insertion silently move an ADD.
    Pointer serialization is sufficient here: no referenced or query-only
    content is opened or copied into the digest.
    """
    if not isinstance(ctx, Context):
        raise AtomizeGroundingError(
            "Atomize grounding Context digest requires a Context."
        )
    return atomize_grounding_canonical_digest(ctx.to_dict())


@dataclass(frozen=True)
class AtomizeGroundingBindings:
    """Immutable snapshots against which one conversation was opened."""

    context_uid: str
    context_name: str
    context_digest: str
    analysis_uid: str
    analysis_digest: str
    workbench_uid: str
    workbench_digest: str
    response_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "context": {
                "uid": self.context_uid,
                "name": self.context_name,
                "digest": self.context_digest,
            },
            "analysis": {
                "uid": self.analysis_uid,
                "digest": self.analysis_digest,
            },
            "workbench": {
                "uid": self.workbench_uid,
                "digest": self.workbench_digest,
                "response_digest": self.response_digest,
            },
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingBindings":
        data = _exact_dict(
            value,
            {"context", "analysis", "workbench"},
            "atomize grounding bindings",
        )
        context = _exact_dict(
            data["context"],
            {"uid", "name", "digest"},
            "atomize grounding Context binding",
        )
        analysis = _exact_dict(
            data["analysis"],
            {"uid", "digest"},
            "atomize grounding analysis binding",
        )
        workbench = _exact_dict(
            data["workbench"],
            {"uid", "digest", "response_digest"},
            "atomize grounding workbench binding",
        )
        return cls(
            context_uid=_canonical_uuid(
                context["uid"],
                "atomize grounding Context uid",
            ),
            context_name=_string(
                context["name"],
                "atomize grounding Context name",
                limit=ATOMIZE_GROUNDING_NAME_LIMIT,
            ),
            context_digest=_digest(
                context["digest"],
                "atomize grounding Context digest",
            ),
            analysis_uid=_canonical_uuid(
                analysis["uid"],
                "atomize grounding analysis uid",
            ),
            analysis_digest=_digest(
                analysis["digest"],
                "atomize grounding analysis digest",
            ),
            workbench_uid=_canonical_uuid(
                workbench["uid"],
                "atomize grounding workbench uid",
            ),
            workbench_digest=_digest(
                workbench["digest"],
                "atomize grounding workbench digest",
            ),
            response_digest=_digest(
                workbench["response_digest"],
                "atomize grounding response digest",
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingAnchor:
    """The selected issue, including its irreducible unary or pair shape."""

    issue_uid: str
    kind: AtomizeGroundingIssueKind
    arity: AtomizeGroundingArity
    source_uids: tuple[str, ...]
    issue_digest: str
    selected_reading_uid: str | None = None
    selected_reading_text: str = ""
    workbench_response: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_uid": self.issue_uid,
            "kind": self.kind,
            "arity": self.arity,
            "source_uids": list(self.source_uids),
            "issue_digest": self.issue_digest,
            "selected_reading_uid": self.selected_reading_uid,
            "selected_reading_text": self.selected_reading_text,
            "workbench_response": self.workbench_response,
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingAnchor":
        data = _exact_dict(
            value,
            {
                "issue_uid",
                "kind",
                "arity",
                "source_uids",
                "issue_digest",
                "selected_reading_uid",
                "selected_reading_text",
                "workbench_response",
            },
            "atomize grounding anchor",
        )
        arity = _literal(
            data["arity"],
            _ARITIES,
            "atomize grounding anchor arity",
        )
        sources = _identifiers(
            data["source_uids"],
            "atomize grounding anchor source uid",
            uuids=True,
        )
        expected_count = 1 if arity == "UNARY" else 2
        if len(sources) != expected_count:
            raise AtomizeGroundingError(
                "Atomize grounding anchor arity does not match its sources."
            )
        selected = data["selected_reading_uid"]
        if selected is not None and not isinstance(selected, str):
            raise AtomizeGroundingError(
                "Invalid atomize grounding selected reading uid."
            )
        selected_text = _string(
            data["selected_reading_text"],
            "atomize grounding selected reading text",
            empty=True,
        )
        if (selected is None) != (selected_text == ""):
            raise AtomizeGroundingError(
                "A selected atomize grounding reading requires its exact "
                "text, and unselected anchors cannot carry reading text."
            )
        return cls(
            issue_uid=_identifier(
                data["issue_uid"],
                "atomize grounding anchor issue uid",
            ),
            kind=_literal(
                data["kind"],
                _ISSUE_KINDS,
                "atomize grounding anchor issue kind",
            ),  # type: ignore[arg-type]
            arity=arity,  # type: ignore[arg-type]
            source_uids=sources,
            issue_digest=_digest(
                data["issue_digest"],
                "atomize grounding anchor issue digest",
            ),
            selected_reading_uid=(
                None
                if selected is None
                else _identifier(
                    selected,
                    "atomize grounding selected reading uid",
                )
            ),
            selected_reading_text=selected_text,
            workbench_response=_string(
                data["workbench_response"],
                "atomize grounding workbench response",
                empty=True,
            ),
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


@dataclass(frozen=True)
class AtomizeGroundingApplication:
    """Receipt recorded only after a command transaction has succeeded."""

    change_set_digest: str
    checkpoint_uid: str
    proposal_uids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "change_set_digest": self.change_set_digest,
            "checkpoint_uid": self.checkpoint_uid,
            "proposal_uids": list(self.proposal_uids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingApplication":
        data = _exact_dict(
            value,
            {"change_set_digest", "checkpoint_uid", "proposal_uids"},
            "atomize grounding application",
        )
        return cls(
            change_set_digest=_digest(
                data["change_set_digest"],
                "atomize grounding change-set digest",
            ),
            checkpoint_uid=_canonical_uuid(
                data["checkpoint_uid"],
                "atomize grounding checkpoint uid",
            ),
            proposal_uids=_identifiers(
                data["proposal_uids"],
                "atomize grounding applied proposal uid",
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingChangeSet:
    """A pure application plan; creating it does not mutate any Memory."""

    session_uid: str
    turn_uid: str
    context_uid: str
    context_digest: str
    analysis_digest: str
    workbench_digest: str
    response_digest: str
    proposals: tuple[AtomizeGroundingProposal, ...]
    digest: str

    def _payload(self) -> dict[str, object]:
        return {
            "session_uid": self.session_uid,
            "turn_uid": self.turn_uid,
            "context_uid": self.context_uid,
            "context_digest": self.context_digest,
            "analysis_digest": self.analysis_digest,
            "workbench_digest": self.workbench_digest,
            "response_digest": self.response_digest,
            "proposals": [proposal.to_dict() for proposal in self.proposals],
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        session_uid: str,
        turn_uid: str,
        bindings: AtomizeGroundingBindings,
        proposals: Iterable[AtomizeGroundingProposal],
    ) -> "AtomizeGroundingChangeSet":
        parsed = tuple(proposals)
        if not parsed or any(
            not isinstance(proposal, AtomizeGroundingProposal)
            for proposal in parsed
        ):
            raise AtomizeGroundingError(
                "Atomize grounding change sets require accepted proposals."
            )
        draft = cls(
            session_uid=_canonical_uuid(
                session_uid,
                "atomize grounding change-set session uid",
            ),
            turn_uid=_canonical_uuid(
                turn_uid,
                "atomize grounding change-set turn uid",
            ),
            context_uid=bindings.context_uid,
            context_digest=bindings.context_digest,
            analysis_digest=bindings.analysis_digest,
            workbench_digest=bindings.workbench_digest,
            response_digest=bindings.response_digest,
            proposals=parsed,
            digest="",
        )
        return replace(
            draft,
            digest=atomize_grounding_canonical_digest(draft._payload()),
        )

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingChangeSet":
        data = _exact_dict(
            value,
            {
                "session_uid",
                "turn_uid",
                "context_uid",
                "context_digest",
                "analysis_digest",
                "workbench_digest",
                "response_digest",
                "proposals",
                "digest",
            },
            "atomize grounding change set",
        )
        proposals = tuple(
            AtomizeGroundingProposal.from_dict(item)
            for item in _list(
                data["proposals"],
                "atomize grounding change-set proposals",
            )
        )
        if not proposals or len({item.uid for item in proposals}) != len(
            proposals
        ):
            raise AtomizeGroundingError(
                "Invalid atomize grounding change-set proposals."
            )
        result = cls(
            session_uid=_canonical_uuid(
                data["session_uid"],
                "atomize grounding change-set session uid",
            ),
            turn_uid=_canonical_uuid(
                data["turn_uid"],
                "atomize grounding change-set turn uid",
            ),
            context_uid=_canonical_uuid(
                data["context_uid"],
                "atomize grounding change-set Context uid",
            ),
            context_digest=_digest(
                data["context_digest"],
                "atomize grounding change-set Context digest",
            ),
            analysis_digest=_digest(
                data["analysis_digest"],
                "atomize grounding change-set analysis digest",
            ),
            workbench_digest=_digest(
                data["workbench_digest"],
                "atomize grounding change-set workbench digest",
            ),
            response_digest=_digest(
                data["response_digest"],
                "atomize grounding change-set response digest",
            ),
            proposals=proposals,
            digest=_digest(
                data["digest"],
                "atomize grounding change-set digest",
            ),
        )
        if result.digest != atomize_grounding_canonical_digest(
            result._payload()
        ):
            raise AtomizeGroundingError(
                "Atomize grounding change-set digest does not match."
            )
        return result


@dataclass
class AtomizeGroundingSession:
    """One resumable human-like grounding conversation around an issue."""

    uid: str
    bindings: AtomizeGroundingBindings
    anchor: AtomizeGroundingAnchor
    state: AtomizeGroundingState = "AWAITING_REPLY"
    turns: tuple[AtomizeGroundingTurn, ...] = ()
    decisions: tuple[AtomizeGroundingDecision, ...] = ()
    application: AtomizeGroundingApplication | None = None

    @classmethod
    def create(
        cls,
        *,
        bindings: AtomizeGroundingBindings,
        anchor: AtomizeGroundingAnchor,
    ) -> "AtomizeGroundingSession":
        if not isinstance(bindings, AtomizeGroundingBindings):
            raise AtomizeGroundingError(
                "Invalid atomize grounding bindings."
            )
        if not isinstance(anchor, AtomizeGroundingAnchor):
            raise AtomizeGroundingError("Invalid atomize grounding anchor.")
        session = cls(
            uid=str(uuid.uuid4()),
            bindings=bindings,
            anchor=anchor,
        )
        return cls.from_dict(session.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": ATOMIZE_GROUNDING_SCHEMA_VERSION,
            "uid": self.uid,
            "bindings": self.bindings.to_dict(),
            "anchor": self.anchor.to_dict(),
            "state": self.state,
            "turns": [turn.to_dict() for turn in self.turns],
            "decisions": [
                decision.to_dict() for decision in self.decisions
            ],
            "application": (
                self.application.to_dict()
                if self.application is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingSession":
        if (
            isinstance(value, dict)
            and not isinstance(value.get("schema_version"), bool)
            and value.get("schema_version")
            == ATOMIZE_GROUNDING_LEGACY_SCHEMA_VERSION
        ):
            # Version 1 predates explicit saved-workbench evidence and
            # provider-judged answer links. Preserve its honest empty meaning
            # rather than inventing either while upgrading the durable shape.
            value = json.loads(json.dumps(value))
            value["schema_version"] = ATOMIZE_GROUNDING_SCHEMA_VERSION
            anchor = value.get("anchor")
            if isinstance(anchor, dict):
                anchor.setdefault("selected_reading_uid", None)
                anchor.setdefault("selected_reading_text", "")
                anchor.setdefault("workbench_response", "")
            turns = value.get("turns")
            if isinstance(turns, list):
                for turn in turns:
                    if not isinstance(turn, dict):
                        continue
                    assessment = turn.get("assessment")
                    if isinstance(assessment, dict):
                        assessment.setdefault(
                            "answered_question_uids",
                            list(turn.get("answers_question_uids", [])),
                        )
        data = _exact_dict(
            value,
            {
                "schema_version",
                "uid",
                "bindings",
                "anchor",
                "state",
                "turns",
                "decisions",
                "application",
            },
            "atomize grounding session",
        )
        schema_version = data["schema_version"]
        if (
            isinstance(schema_version, bool)
            or schema_version != ATOMIZE_GROUNDING_SCHEMA_VERSION
        ):
            raise AtomizeGroundingError(
                "Unsupported atomize grounding schema version."
            )
        turns = tuple(
            AtomizeGroundingTurn.from_dict(item)
            for item in _list(
                data["turns"],
                "atomize grounding turns",
            )
        )
        decisions = tuple(
            AtomizeGroundingDecision.from_dict(item)
            for item in _list(
                data["decisions"],
                "atomize grounding decisions",
            )
        )
        raw_application = data["application"]
        session = cls(
            uid=_canonical_uuid(
                data["uid"],
                "atomize grounding session uid",
            ),
            bindings=AtomizeGroundingBindings.from_dict(data["bindings"]),
            anchor=AtomizeGroundingAnchor.from_dict(data["anchor"]),
            state=_literal(
                data["state"],
                _STATES,
                "atomize grounding state",
            ),  # type: ignore[arg-type]
            turns=turns,
            decisions=decisions,
            application=(
                None
                if raw_application is None
                else AtomizeGroundingApplication.from_dict(raw_application)
            ),
        )
        session._validate_history()
        return session

    @property
    def current_turn(self) -> AtomizeGroundingTurn | None:
        return self.turns[-1] if self.turns else None

    @property
    def current_assessment(self) -> AtomizeGroundingAssessment | None:
        turn = self.current_turn
        return turn.assessment if turn is not None else None

    @property
    def active_understanding(self) -> tuple[str, ...]:
        assessment = self.current_assessment
        return (
            assessment.active_understanding
            if assessment is not None
            else ()
        )

    def start_turn(
        self,
        comment: str,
        *,
        revision: AtomizeGroundingRevision | None = None,
        revises_turn_uids: Iterable[str] = (),
        answers_question_uids: Iterable[str] = (),
    ) -> AtomizeGroundingTurn:
        """Stage a user turn without claiming that it has been understood."""
        if self.state in {"APPLIED", "KEPT_REVIEW_ONLY"}:
            raise AtomizeGroundingError(
                f"Cannot add a turn while grounding is {self.state}."
            )
        parsed_revises = tuple(revises_turn_uids)
        parsed_answers = tuple(answers_question_uids)
        relation = revision or ("INITIAL" if not self.turns else "EXTEND")
        turn = AtomizeGroundingTurn.from_dict(
            {
                "uid": str(uuid.uuid4()),
                "sequence": len(self.turns),
                "revision": relation,
                "comment": comment,
                "revises_turn_uids": list(parsed_revises),
                "answers_question_uids": list(parsed_answers),
                "assessment": None,
            }
        )
        self.turns = (*self.turns, turn)
        self.state = "AWAITING_REPLY"
        self.application = None
        self._validate_history()
        return turn

    def record_assessment(
        self,
        turn_uid: str,
        assessment: AtomizeGroundingAssessment,
    ) -> None:
        """Attach the cumulative judgment for the only pending user turn."""
        if self.current_turn is None:
            raise AtomizeGroundingError(
                "No atomize grounding turn is awaiting assessment."
            )
        if self.current_turn.uid != turn_uid:
            raise AtomizeGroundingError(
                "Only the latest atomize grounding turn can be assessed."
            )
        if self.current_turn.assessment is not None:
            raise AtomizeGroundingError(
                "The latest atomize grounding turn is already assessed."
            )
        if not isinstance(assessment, AtomizeGroundingAssessment):
            raise AtomizeGroundingError(
                "Invalid atomize grounding assessment."
            )
        self.turns = (
            *self.turns[:-1],
            replace(
                self.current_turn,
                answers_question_uids=assessment.answered_question_uids,
                assessment=assessment,
            ),
        )
        if assessment.ready_to_apply:
            self.state = "READY_TO_APPLY"
        else:
            self.state = "AWAITING_REPLY"
        self._validate_history()

    def decide(
        self,
        proposal_uid: str,
        action: AtomizeGroundingDecisionAction,
        *,
        rationale: str = "",
    ) -> AtomizeGroundingDecision:
        """Append a user decision without losing earlier decision history."""
        if self.state != "READY_TO_APPLY":
            raise AtomizeGroundingError(
                "Proposal decisions require a ready grounding session."
            )
        current = self.current_assessment
        assert self.current_turn is not None and current is not None
        if proposal_uid not in {
            proposal.uid for proposal in current.proposals
        }:
            raise AtomizeGroundingError(
                "Only a current grounding proposal can be decided."
            )
        decision = AtomizeGroundingDecision.from_dict(
            {
                # A receipt-save retry must recreate the same authority record
                # that was written into the successful checkpoint. Sequence,
                # proposal, action, turn, and rationale fully identify this
                # append-only decision within one session.
                "uid": str(
                    uuid.uuid5(
                        uuid.UUID(self.uid),
                        "\x1f".join(
                            (
                                str(len(self.decisions)),
                                proposal_uid,
                                action,
                                self.current_turn.uid,
                                rationale,
                            )
                        ),
                    )
                ),
                "sequence": len(self.decisions),
                "proposal_uid": proposal_uid,
                "action": action,
                "after_turn_uid": self.current_turn.uid,
                "rationale": rationale,
            }
        )
        self.decisions = (*self.decisions, decision)
        self._validate_history()
        return decision

    def effective_decision(
        self,
        proposal_uid: str,
    ) -> AtomizeGroundingDecision | None:
        for decision in reversed(self.decisions):
            if decision.proposal_uid == proposal_uid:
                return decision
        return None

    def prepare_changes(self) -> AtomizeGroundingChangeSet:
        """Build an exact plan once every current proposal is decided."""
        if self.state != "READY_TO_APPLY":
            raise AtomizeGroundingError(
                "Atomize grounding is not ready to prepare changes."
            )
        turn = self.current_turn
        assessment = self.current_assessment
        assert turn is not None and assessment is not None
        accepted: list[AtomizeGroundingProposal] = []
        for proposal in assessment.proposals:
            decision = self.effective_decision(proposal.uid)
            if decision is None or decision.action == "DEFER":
                raise AtomizeGroundingError(
                    "Every current proposal must be accepted or rejected."
                )
            if (
                proposal.necessity == "REQUIRED"
                and decision.action != "ACCEPT"
            ):
                raise AtomizeGroundingError(
                    "A required proposal was rejected; continue grounding "
                    "before preparing changes."
                )
            if decision.action == "ACCEPT":
                accepted.append(proposal)
        if not accepted:
            raise AtomizeGroundingError(
                "No atomize grounding changes were accepted."
            )
        return AtomizeGroundingChangeSet.create(
            session_uid=self.uid,
            turn_uid=turn.uid,
            bindings=self.bindings,
            proposals=accepted,
        )

    def record_application(
        self,
        *,
        change_set_digest: str,
        checkpoint_uid: str,
    ) -> None:
        """Record a receipt after an external transaction has applied a plan."""
        change_set = self.prepare_changes()
        if change_set.digest != change_set_digest:
            raise AtomizeGroundingError(
                "Applied change-set digest does not match the prepared plan."
            )
        self.application = AtomizeGroundingApplication.from_dict(
            {
                "change_set_digest": change_set_digest,
                "checkpoint_uid": checkpoint_uid,
                "proposal_uids": [
                    proposal.uid for proposal in change_set.proposals
                ],
            }
        )
        self.state = "APPLIED"
        self._validate_history()

    def clear_application(
        self,
        *,
        change_set_digest: str,
        checkpoint_uid: str,
    ) -> None:
        """Return one exact application to its reviewed ready state."""
        if self.state != "APPLIED" or self.application is None:
            raise AtomizeGroundingError(
                "Atomize grounding application is not currently applied."
            )
        if (
            self.application.change_set_digest != change_set_digest
            or self.application.checkpoint_uid != checkpoint_uid
        ):
            raise AtomizeGroundingError(
                "Atomize grounding receipt does not match this undo."
            )
        self.application = None
        self.state = "READY_TO_APPLY"
        self._validate_history()

    def keep_review_only(self) -> None:
        """Close the dialogue while retaining its evidence without edits."""
        if self.state == "APPLIED":
            raise AtomizeGroundingError(
                "An applied grounding session cannot become review-only."
            )
        self.state = "KEPT_REVIEW_ONLY"
        self.application = None
        self._validate_history()

    def _validate_history(self) -> None:
        turn_by_uid: dict[str, AtomizeGroundingTurn] = {}
        question_turn: dict[str, int] = {}
        proposal_turn: dict[str, int] = {}
        seen_unassessed = False

        for expected_sequence, turn in enumerate(self.turns):
            if turn.sequence != expected_sequence:
                raise AtomizeGroundingError(
                    "Atomize grounding turn sequence is not contiguous."
                )
            if turn.uid in turn_by_uid:
                raise AtomizeGroundingError(
                    "Duplicate atomize grounding turn uid."
                )
            try:
                # Atomize disambiguation is an issue-scoped directional meld.
                # Reuse the same conversational lineage contract while
                # retaining atomize's stricter issue/question/proposal checks
                # and its existing durable schema.
                validate_meld_turn_lineage(
                    sequence=expected_sequence,
                    revision=turn.revision,
                    revises_turn_uids=turn.revises_turn_uids,
                    known_turn_uids=turn_by_uid,
                )
            except MeldError as error:
                message = {
                    "The first meld turn must be INITIAL.": (
                        "The first grounding turn must be INITIAL."
                    ),
                    "Only the first meld turn can be INITIAL.": (
                        "Only the first grounding turn can be INITIAL."
                    ),
                    (
                        "CORRECT and RETRACT meld turns must identify "
                        "revised turns."
                    ): (
                        "CORRECT and RETRACT turns must identify revised "
                        "turns."
                    ),
                    (
                        "A meld turn revises an unknown or future turn."
                    ): (
                        "A grounding turn revises an unknown or future turn."
                    ),
                }.get(str(error), str(error))
                raise AtomizeGroundingError(message) from error
            if not set(turn.answers_question_uids) <= set(question_turn):
                raise AtomizeGroundingError(
                    "A grounding turn answers an unknown or future question."
                )
            if turn.assessment is None:
                seen_unassessed = True
                if expected_sequence != len(self.turns) - 1:
                    raise AtomizeGroundingError(
                        "Only the latest grounding turn may await assessment."
                    )
            elif seen_unassessed:
                raise AtomizeGroundingError(
                    "An assessed grounding turn follows a pending turn."
                )
            else:
                self._validate_assessment(
                    turn,
                    known_turn_uids={
                        *turn_by_uid,
                        turn.uid,
                    },
                )
                assessment = turn.assessment
                assert assessment is not None
                for effect in assessment.downstream:
                    if effect.issue_uid == self.anchor.issue_uid:
                        raise AtomizeGroundingError(
                            "The anchor issue cannot be its own downstream "
                            "effect."
                        )
                for question in assessment.follow_ups:
                    if question.uid in question_turn:
                        raise AtomizeGroundingError(
                            "Duplicate atomize grounding follow-up uid "
                            "across turns."
                        )
                    question_turn[question.uid] = expected_sequence
                for proposal in assessment.proposals:
                    if proposal.uid in proposal_turn:
                        raise AtomizeGroundingError(
                            "Duplicate atomize grounding proposal uid "
                            "across turns."
                        )
                    proposal_turn[proposal.uid] = expected_sequence
            turn_by_uid[turn.uid] = turn

        if len({decision.uid for decision in self.decisions}) != len(
            self.decisions
        ):
            raise AtomizeGroundingError(
                "Duplicate atomize grounding decision uid."
            )
        for expected_sequence, decision in enumerate(self.decisions):
            if decision.sequence != expected_sequence:
                raise AtomizeGroundingError(
                    "Atomize grounding decision sequence is not contiguous."
                )
            if decision.proposal_uid not in proposal_turn:
                raise AtomizeGroundingError(
                    "A grounding decision targets an unknown proposal."
                )
            if decision.after_turn_uid not in turn_by_uid:
                raise AtomizeGroundingError(
                    "A grounding decision names an unknown turn."
                )
            decision_turn = turn_by_uid[decision.after_turn_uid].sequence
            if proposal_turn[decision.proposal_uid] > decision_turn:
                raise AtomizeGroundingError(
                    "A grounding decision precedes its proposal."
                )

        self._validate_state()

    def _validate_assessment(
        self,
        turn: AtomizeGroundingTurn,
        *,
        known_turn_uids: set[str],
    ) -> None:
        assessment = turn.assessment
        assert assessment is not None
        if (
            assessment.answered_question_uids
            != turn.answers_question_uids
        ):
            raise AtomizeGroundingError(
                "A grounding assessment answer link does not match its turn."
            )
        known_issue_uids = {
            self.anchor.issue_uid,
            *(effect.issue_uid for effect in assessment.downstream),
        }
        issue_sources = {
            self.anchor.issue_uid: set(self.anchor.source_uids),
            **{
                effect.issue_uid: set(effect.source_uids)
                for effect in assessment.downstream
            },
        }
        for question in assessment.follow_ups:
            if not set(question.issue_uids) <= known_issue_uids:
                raise AtomizeGroundingError(
                    "A follow-up references an issue outside its assessment."
                )
        anchor_sources = set(self.anchor.source_uids)
        for proposal in assessment.proposals:
            if not set(proposal.issue_uids) <= known_issue_uids:
                raise AtomizeGroundingError(
                    "A proposal references an issue outside its assessment."
                )
            if not set(proposal.grounded_by_turn_uids) <= known_turn_uids:
                raise AtomizeGroundingError(
                    "A proposal is grounded by an unknown or future turn."
                )
            if (
                proposal.operation == "EDIT"
                and proposal.memory_uid
                not in {
                    source_uid
                    for issue_uid in proposal.issue_uids
                    for source_uid in issue_sources[issue_uid]
                }
            ):
                raise AtomizeGroundingError(
                    "An EDIT proposal must target a source Memory of one of "
                    "its linked issues."
                )
            if (
                proposal.operation == "ADD"
                and proposal.memory_uid in anchor_sources
            ):
                raise AtomizeGroundingError(
                    "An ADD proposal cannot reuse an anchor Memory uid."
                )

    def _validate_state(self) -> None:
        if not self.turns:
            if (
                self.state
                not in {"AWAITING_REPLY", "KEPT_REVIEW_ONLY"}
                or self.decisions
                or self.application is not None
            ):
                raise AtomizeGroundingError(
                    "Invalid empty atomize grounding session state."
                )
            return

        latest = self.current_turn
        assert latest is not None
        if latest.assessment is None:
            if self.state not in {
                "AWAITING_REPLY",
                "KEPT_REVIEW_ONLY",
            }:
                raise AtomizeGroundingError(
                    "A pending grounding turn must await a reply."
                )

        assessment = latest.assessment
        if assessment is not None:
            retracted_turn_uids = {
                revised_uid
                for turn in self.turns
                if turn.revision == "RETRACT"
                for revised_uid in turn.revises_turn_uids
            }
            correcting_turns_by_target: dict[str, set[str]] = {}
            for turn in self.turns:
                if turn.revision != "CORRECT":
                    continue
                for revised_uid in turn.revises_turn_uids:
                    correcting_turns_by_target.setdefault(
                        revised_uid,
                        set(),
                    ).add(turn.uid)
            for proposal in assessment.proposals:
                cited = set(proposal.grounded_by_turn_uids)
                if cited & retracted_turn_uids:
                    raise AtomizeGroundingError(
                        "A current grounding proposal cannot cite a retracted "
                        "turn as active evidence."
                    )
                for corrected_uid in cited & correcting_turns_by_target.keys():
                    if not correcting_turns_by_target[corrected_uid] <= cited:
                        raise AtomizeGroundingError(
                            "A current grounding proposal that cites a "
                            "corrected turn must also cite its correcting "
                            "turn."
                        )
        if (
            self.state == "AWAITING_REPLY"
            and assessment is not None
            and assessment.ready_to_apply
        ):
            raise AtomizeGroundingError(
                "A ready grounding assessment cannot remain AWAITING_REPLY."
            )
        if self.state == "READY_TO_APPLY":
            if (
                assessment is None
                or not assessment.ready_to_apply
            ):
                raise AtomizeGroundingError(
                    "Invalid READY_TO_APPLY grounding state."
                )
        if self.state == "APPLIED":
            if (
                assessment is None
                or not assessment.ready_to_apply
                or self.application is None
            ):
                raise AtomizeGroundingError(
                    "Applied grounding state requires a ready assessment and "
                    "an application receipt."
                )
            accepted: list[AtomizeGroundingProposal] = []
            for proposal in assessment.proposals:
                decision = self.effective_decision(proposal.uid)
                if decision is None or decision.action == "DEFER":
                    raise AtomizeGroundingError(
                        "Applied grounding requires a final decision for every "
                        "current proposal."
                    )
                if (
                    proposal.necessity == "REQUIRED"
                    and decision.action != "ACCEPT"
                ):
                    raise AtomizeGroundingError(
                        "Applied grounding cannot reject a required proposal."
                    )
                if decision.action == "ACCEPT":
                    accepted.append(proposal)
            if not accepted:
                raise AtomizeGroundingError(
                    "Applied grounding has no accepted proposal."
                )
            expected = AtomizeGroundingChangeSet.create(
                session_uid=self.uid,
                turn_uid=latest.uid,
                bindings=self.bindings,
                proposals=accepted,
            )
            if (
                self.application.proposal_uids
                != tuple(proposal.uid for proposal in accepted)
                or self.application.change_set_digest != expected.digest
            ):
                raise AtomizeGroundingError(
                    "Applied grounding receipt does not match its accepted "
                    "change set."
                )
        elif self.application is not None:
            raise AtomizeGroundingError(
                "Only an applied grounding session can carry a receipt."
            )


def prepare_atomize_grounding_changes(
    session: AtomizeGroundingSession,
) -> AtomizeGroundingChangeSet:
    """Pure convenience wrapper for command-layer integrations."""
    if not isinstance(session, AtomizeGroundingSession):
        raise AtomizeGroundingError(
            "Expected an AtomizeGroundingSession."
        )
    return session.prepare_changes()
