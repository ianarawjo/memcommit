"""Strict persistence tests for conversational atomize grounding."""
from __future__ import annotations

import copy
import hashlib
import uuid

import pytest

from memcommit.application.operations.atomize.grounding import (
    ATOMIZE_GROUNDING_SCHEMA_VERSION,
    AtomizeGroundingAnchor,
    AtomizeGroundingAssessment,
    AtomizeGroundingBindings,
    AtomizeGroundingChangeSet,
    AtomizeGroundingError,
    AtomizeGroundingSession,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bindings() -> AtomizeGroundingBindings:
    return AtomizeGroundingBindings.from_dict(
        {
            "context": {
                "uid": _uuid(),
                "name": "temp/task-1",
                "digest": _digest("context"),
            },
            "analysis": {
                "uid": _uuid(),
                "digest": _digest("analysis"),
            },
            "workbench": {
                "uid": _uuid(),
                "digest": _digest("workbench"),
                "response_digest": _digest("responses"),
            },
        }
    )


def _anchor(*, pair: bool = False) -> AtomizeGroundingAnchor:
    sources = [_uuid(), _uuid()] if pair else [_uuid()]
    return AtomizeGroundingAnchor.from_dict(
        {
            "issue_uid": "conflict:card-app" if pair else "ambiguity:card",
            "kind": "CONFLICT" if pair else "AMBIGUITY",
            "arity": "PAIR" if pair else "UNARY",
            "source_uids": sources,
            "issue_digest": _digest("issue"),
            "selected_reading_uid": None,
            "selected_reading_text": "",
            "workbench_response": "",
        }
    )


def _assessment(
    *,
    turn_uid: str,
    anchor_uid: str,
    downstream_uid: str,
    downstream_source_uid: str,
    question_uid: str | None,
    proposal_uid: str,
    memory_uid: str,
    resolved: bool,
    answered_question_uids: tuple[str, ...] = (),
) -> AtomizeGroundingAssessment:
    question_uids = [question_uid] if question_uid else []
    follow_ups = (
        [
            {
                "uid": question_uid,
                "kind": "SCOPE_CHECK",
                "priority": "REQUIRED",
                "text": "Does the staff entrance use the same physical card?",
                "reason": "The comment establishes only the main entrance.",
                "issue_uids": [downstream_uid],
            }
        ]
        if question_uid
        else []
    )
    return AtomizeGroundingAssessment.from_dict(
        {
            "provider_response_digest": _digest(
                f"provider:{proposal_uid}"
            ),
            "active_understanding": [
                "The Main Building entrance accepts physical NFC cards only."
            ],
            "direct": {
                "status": "RESOLVED" if resolved else "PARTIAL",
                "explanation": "The user disallowed app authentication.",
                "proposal_uids": [proposal_uid],
                "question_uids": [],
            },
            "downstream": [
                {
                    "issue_uid": downstream_uid,
                    "source_uids": [downstream_source_uid],
                    "effect": (
                        "RESOLVES" if resolved else "NEEDS_CONFIRMATION"
                    ),
                    "explanation": "The same authentication phrase recurs.",
                    "proposal_uids": [],
                    "question_uids": question_uids,
                }
            ],
            "follow_ups": follow_ups,
            "proposals": [
                {
                    "uid": proposal_uid,
                    "operation": "EDIT",
                    "necessity": "REQUIRED",
                    "memory_uid": memory_uid,
                    "expected_content_digest": _digest("old"),
                    "content": "Use a physical NFC card; do not suggest the app.",
                    "position": None,
                    "reason": "The old app guidance conflicts with the comment.",
                    "issue_uids": [anchor_uid],
                    "grounded_by_turn_uids": [turn_uid],
                }
            ],
            "answered_question_uids": list(answered_question_uids),
        }
    )


def test_pair_anchor_round_trips_without_flattening_arity():
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=_anchor(pair=True),
    )

    data = session.to_dict()
    restored = AtomizeGroundingSession.from_dict(data)

    assert data["schema_version"] == ATOMIZE_GROUNDING_SCHEMA_VERSION
    assert data["state"] == "AWAITING_REPLY"
    assert data["anchor"]["arity"] == "PAIR"
    assert len(data["anchor"]["source_uids"]) == 2
    assert restored.to_dict() == data


def test_legacy_v1_session_migrates_without_inventing_workbench_evidence():
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=_anchor(),
    )
    legacy = session.to_dict()
    legacy["schema_version"] = 1
    del legacy["anchor"]["selected_reading_uid"]
    del legacy["anchor"]["selected_reading_text"]
    del legacy["anchor"]["workbench_response"]

    restored = AtomizeGroundingSession.from_dict(legacy)

    assert restored.to_dict()["schema_version"] == (
        ATOMIZE_GROUNDING_SCHEMA_VERSION
    )
    assert restored.anchor.selected_reading_uid is None
    assert restored.anchor.selected_reading_text == ""
    assert restored.anchor.workbench_response == ""


def test_correction_round_can_answer_follow_up_and_prepare_exact_change_set():
    anchor = _anchor()
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=anchor,
    )
    downstream_uid = "atomize:staff-entrance"
    downstream_source_uid = _uuid()
    edited_memory_uid = anchor.source_uids[0]

    first = session.start_turn(
        "This entrance accepts a physical NFC card, not the app."
    )
    session.record_assessment(
        first.uid,
        _assessment(
            turn_uid=first.uid,
            anchor_uid=anchor.issue_uid,
            downstream_uid=downstream_uid,
            downstream_source_uid=downstream_source_uid,
            question_uid="question:staff-card",
            proposal_uid="proposal:first-edit",
            memory_uid=edited_memory_uid,
            resolved=False,
        ),
    )
    assert session.state == "AWAITING_REPLY"

    second = session.start_turn(
        "The app guidance was wrong, and the staff entrance uses the same card.",
        revision="CORRECT",
        revises_turn_uids=(first.uid,),
        answers_question_uids=("question:staff-card",),
    )
    session.record_assessment(
        second.uid,
        _assessment(
            turn_uid=second.uid,
            anchor_uid=anchor.issue_uid,
            downstream_uid=downstream_uid,
            downstream_source_uid=downstream_source_uid,
            question_uid=None,
            proposal_uid="proposal:final-edit",
            memory_uid=edited_memory_uid,
            resolved=True,
            answered_question_uids=("question:staff-card",),
        ),
    )

    assert session.state == "READY_TO_APPLY"
    assert session.active_understanding == (
        "The Main Building entrance accepts physical NFC cards only.",
    )
    session.decide("proposal:final-edit", "ACCEPT")
    change_set = session.prepare_changes()
    restored = AtomizeGroundingChangeSet.from_dict(change_set.to_dict())

    assert restored.to_dict() == change_set.to_dict()
    assert [item.uid for item in change_set.proposals] == [
        "proposal:final-edit"
    ]
    # Preparing an accepted plan remains non-mutating session state.
    assert session.state == "READY_TO_APPLY"
    assert session.application is None


def test_current_proposal_cannot_hide_a_correction_to_its_cited_turn():
    anchor = _anchor()
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=anchor,
    )
    first = session.start_turn("The entrance accepts a physical card.")
    session.record_assessment(
        first.uid,
        _assessment(
            turn_uid=first.uid,
            anchor_uid=anchor.issue_uid,
            downstream_uid="atomize:staff",
            downstream_source_uid=_uuid(),
            question_uid=None,
            proposal_uid="proposal:first",
            memory_uid=anchor.source_uids[0],
            resolved=True,
        ),
    )
    second = session.start_turn(
        "Correction: the card must be the physical NFC card.",
        revision="CORRECT",
        revises_turn_uids=(first.uid,),
    )

    with pytest.raises(
        AtomizeGroundingError,
        match="must also cite its correcting turn",
    ):
        session.record_assessment(
            second.uid,
            _assessment(
                turn_uid=first.uid,
                anchor_uid=anchor.issue_uid,
                downstream_uid="atomize:staff",
                downstream_source_uid=_uuid(),
                question_uid=None,
                proposal_uid="proposal:stale",
                memory_uid=anchor.source_uids[0],
                resolved=True,
            ),
        )


def test_edit_proposal_cannot_escape_its_linked_issue_sources():
    anchor = _anchor()
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=anchor,
    )
    turn = session.start_turn("Only a physical NFC card works.")

    with pytest.raises(
        AtomizeGroundingError,
        match="source Memory of one of its linked issues",
    ):
        session.record_assessment(
            turn.uid,
            _assessment(
                turn_uid=turn.uid,
                anchor_uid=anchor.issue_uid,
                downstream_uid="atomize:staff",
                downstream_source_uid=_uuid(),
                question_uid=None,
                proposal_uid="proposal:unrelated-edit",
                memory_uid=_uuid(),
                resolved=True,
            ),
        )


def test_application_receipt_and_keep_review_only_are_explicit_terminal_states():
    anchor = _anchor()
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=anchor,
    )
    turn = session.start_turn("Only the physical card works.")
    session.record_assessment(
        turn.uid,
        _assessment(
            turn_uid=turn.uid,
            anchor_uid=anchor.issue_uid,
            downstream_uid="atomize:staff",
            downstream_source_uid=_uuid(),
            question_uid=None,
            proposal_uid="proposal:edit",
            memory_uid=anchor.source_uids[0],
            resolved=True,
        ),
    )
    session.decide("proposal:edit", "ACCEPT")
    change_set = session.prepare_changes()
    checkpoint_uid = _uuid()
    session.record_application(
        change_set_digest=change_set.digest,
        checkpoint_uid=checkpoint_uid,
    )

    restored = AtomizeGroundingSession.from_dict(session.to_dict())
    assert restored.state == "APPLIED"
    assert restored.application is not None
    assert restored.application.checkpoint_uid == checkpoint_uid

    review_only = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=_anchor(),
    )
    review_only.keep_review_only()
    assert review_only.state == "KEPT_REVIEW_ONLY"


def test_loader_rejects_ready_state_mismatch_and_tampered_applied_receipt():
    anchor = _anchor()
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=anchor,
    )
    turn = session.start_turn("Only the physical card works.")
    session.record_assessment(
        turn.uid,
        _assessment(
            turn_uid=turn.uid,
            anchor_uid=anchor.issue_uid,
            downstream_uid="atomize:staff",
            downstream_source_uid=_uuid(),
            question_uid=None,
            proposal_uid="proposal:edit",
            memory_uid=anchor.source_uids[0],
            resolved=True,
        ),
    )
    ready_data = copy.deepcopy(session.to_dict())
    ready_data["state"] = "AWAITING_REPLY"
    with pytest.raises(
        AtomizeGroundingError,
        match="cannot remain AWAITING_REPLY",
    ):
        AtomizeGroundingSession.from_dict(ready_data)

    session.decide("proposal:edit", "ACCEPT")
    change_set = session.prepare_changes()
    session.record_application(
        change_set_digest=change_set.digest,
        checkpoint_uid=_uuid(),
    )
    applied_data = copy.deepcopy(session.to_dict())
    applied_data["application"]["change_set_digest"] = "0" * 64
    with pytest.raises(
        AtomizeGroundingError,
        match="receipt does not match",
    ):
        AtomizeGroundingSession.from_dict(applied_data)

    rejected_data = copy.deepcopy(session.to_dict())
    rejected_data["decisions"][0]["action"] = "REJECT"
    with pytest.raises(
        AtomizeGroundingError,
        match="cannot reject a required proposal",
    ):
        AtomizeGroundingSession.from_dict(rejected_data)


def test_partial_direct_outcome_cannot_become_ready_from_proposals_alone():
    anchor = _anchor()
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=anchor,
    )
    turn = session.start_turn("The card rule may have one more exception.")
    assessment = _assessment(
        turn_uid=turn.uid,
        anchor_uid=anchor.issue_uid,
        downstream_uid="atomize:staff",
        downstream_source_uid=_uuid(),
        question_uid=None,
        proposal_uid="proposal:partial",
        memory_uid=anchor.source_uids[0],
        resolved=True,
    )
    data = assessment.to_dict()
    data["direct"]["status"] = "PARTIAL"
    partial = AtomizeGroundingAssessment.from_dict(data)

    session.record_assessment(turn.uid, partial)

    assert partial.proposals
    assert not partial.ready_to_apply
    assert session.state == "AWAITING_REPLY"


def test_needs_confirmation_requires_a_blocking_follow_up():
    anchor = _anchor()
    turn_uid = _uuid()
    assessment = _assessment(
        turn_uid=turn_uid,
        anchor_uid=anchor.issue_uid,
        downstream_uid="atomize:staff",
        downstream_source_uid=_uuid(),
        question_uid=None,
        proposal_uid="proposal:unsafe",
        memory_uid=anchor.source_uids[0],
        resolved=True,
    )
    data = assessment.to_dict()
    data["downstream"][0]["effect"] = "NEEDS_CONFIRMATION"

    with pytest.raises(
        AtomizeGroundingError,
        match="requires a blocking follow-up",
    ):
        AtomizeGroundingAssessment.from_dict(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.update({"extra": True}),
        lambda data: data.update({"schema_version": True}),
        lambda data: data["bindings"]["context"].update(
            {"digest": "0" * 63}
        ),
        lambda data: data["anchor"].update({"arity": "PAIR"}),
    ],
)
def test_strict_loader_rejects_unknown_fields_bad_digests_and_wrong_arity(
    mutate,
):
    data = copy.deepcopy(
        AtomizeGroundingSession.create(
            bindings=_bindings(),
            anchor=_anchor(),
        ).to_dict()
    )
    mutate(data)

    with pytest.raises(AtomizeGroundingError):
        AtomizeGroundingSession.from_dict(data)


def test_assessment_rejects_unknown_cross_references_and_add_old_digest():
    anchor = _anchor()
    session = AtomizeGroundingSession.create(
        bindings=_bindings(),
        anchor=anchor,
    )
    turn = session.start_turn("Use the physical card.")
    data = _assessment(
        turn_uid=turn.uid,
        anchor_uid=anchor.issue_uid,
        downstream_uid="atomize:staff",
        downstream_source_uid=_uuid(),
        question_uid=None,
        proposal_uid="proposal:edit",
        memory_uid=anchor.source_uids[0],
        resolved=True,
    ).to_dict()
    data["direct"]["proposal_uids"] = ["proposal:missing"]
    with pytest.raises(AtomizeGroundingError, match="Unknown proposal"):
        AtomizeGroundingAssessment.from_dict(data)

    proposal = copy.deepcopy(data["proposals"][0])
    proposal["operation"] = "ADD"
    with pytest.raises(AtomizeGroundingError, match="cannot expect"):
        from memcommit.application.operations.atomize.grounding import AtomizeGroundingProposal

        AtomizeGroundingProposal.from_dict(proposal)
