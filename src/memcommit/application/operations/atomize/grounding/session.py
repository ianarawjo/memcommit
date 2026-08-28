"""Atomize Grounding session lifecycle, validation, and change preparation."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from typing import Iterable

from memcommit.application.operations.meld.model import (
    MeldError,
    validate_meld_turn_lineage,
)

from .bindings import (
    ATOMIZE_GROUNDING_LEGACY_SCHEMA_VERSION,
    ATOMIZE_GROUNDING_SCHEMA_VERSION,
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingDecisionAction,
    AtomizeGroundingError,
    AtomizeGroundingRevision,
    AtomizeGroundingState,
    _STATES,
    _canonical_uuid,
    _exact_dict,
    _list,
    _literal,
)
from .changes import AtomizeGroundingApplication, AtomizeGroundingChangeSet
from .review import (
    AtomizeGroundingAssessment,
    AtomizeGroundingDecision,
    AtomizeGroundingProposal,
    AtomizeGroundingTurn,
)


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
