"""Semantic-provider boundary tests for conversational atomize grounding."""
from __future__ import annotations

import copy
import hashlib
import json
import uuid

import pytest

import memcommit.ops as ops
from memcommit.atomize import (
    ATOMIZE_RULESET_VERSION,
    AtomizeAnalysisItem,
    AtomizeAnalysisSession,
    AtomizeQualityIssue,
    AtomizeReading,
)
from memcommit.atomize_grounding import (
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingSession,
    atomize_grounding_canonical_digest,
    atomize_grounding_context_digest,
)
from memcommit.atomize_grounding_provider import (
    ATOMIZE_GROUNDING_PAYLOAD_MARKER,
    AtomizeGroundingProviderError,
    assess_atomize_grounding_turn,
)
from memcommit.atomize_workbench import (
    atomize_workbench_issue_digest,
    atomize_workbench_response_digest,
    create_atomize_workbench,
    project_atomize_workbench_findings,
)
from memcommit.context import Context
from memcommit.review import direct_context_digest


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class FakeProvider:
    def __init__(self, responder):
        self.responder = responder
        self.calls: list[tuple[str, str, dict[str, object], dict]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(
            prompt.split(ATOMIZE_GROUNDING_PAYLOAD_MARKER, 1)[1]
        )
        self.calls.append((prompt, operation, output_schema, payload))
        response = self.responder(payload)
        return response if isinstance(response, str) else json.dumps(response)


def _fixture() -> tuple[
    Context,
    AtomizeAnalysisSession,
    AtomizeGroundingSession,
    tuple[str, str, str],
]:
    ctx = ops.init("temp/task-1")
    first = ops.add(
        ctx,
        "Students should be guided to use a physical card or the app.",
    )
    second = ops.add(
        ctx,
        "The staff-only entrance uses the same NFC.",
    )
    third = ops.add(
        ctx,
        "Only a physical NFC card works at the Main Building entrance.",
    )
    items = tuple(
        AtomizeAnalysisItem(
            memory_uid=memory.uid,
            content=memory.content,
            position=position,
            classification="ATOMIC",
            reason_codes=("A01_ONE_FOCUS",),
            children=(),
            reason="The source has one independently revisable focus.",
            lint=(),
        )
        for position, memory in enumerate((first, second, third))
    )
    ambiguity = AtomizeQualityIssue(
        uid=f"ambiguity:{first.uid}",
        kind="AMBIGUITY",
        source_uids=(first.uid,),
        interpretation="COMPETING",
        clarification="REQUIRED",
        conflict=None,
        readings=(
            AtomizeReading(
                uid="reading:physical",
                role="COMPETING",
                label="Give a physical card",
                text="Issue a physical card to the student.",
            ),
            AtomizeReading(
                uid="reading:guide",
                role="COMPETING",
                label="Explain either method",
                text="Tell the student to use either listed method.",
            ),
        ),
        scope_dimensions=(),
        reason="The action and accepted credential are both unclear.",
        question="Should staff issue a card or explain available methods?",
    )
    conflict = AtomizeQualityIssue(
        uid=f"conflict:{second.uid}:{third.uid}",
        kind="CONFLICT",
        source_uids=(second.uid, third.uid),
        interpretation=None,
        clarification=None,
        conflict="MAY",
        readings=(
            AtomizeReading(
                uid="reading:same-physical",
                role="COMPETING",
                label="Same physical credential",
                text="The staff entrance also accepts only the physical card.",
            ),
            AtomizeReading(
                uid="reading:same-mechanism",
                role="COMPETING",
                label="Same NFC mechanism",
                text="The staff entrance shares NFC but may accept an app.",
            ),
        ),
        scope_dimensions=("ACCESS_METHOD",),
        reason="The antecedent of same NFC changes the access rule.",
        question="Does the staff entrance also reject app authentication?",
    )
    analysis = AtomizeAnalysisSession(
        uid=str(uuid.uuid4()),
        created_at="2026-07-29T00:00:00+00:00",
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=direct_context_digest(ctx),
        ruleset_version=ATOMIZE_RULESET_VERSION,
        memory_count=3,
        projected_memory_count=3,
        items=items,
        quality_issues=(ambiguity, conflict),
    )
    workbench = create_atomize_workbench(analysis)
    findings = project_atomize_workbench_findings(analysis)
    anchor_finding = findings[0]
    bindings = AtomizeGroundingBindings.from_dict(
        {
            "context": {
                "uid": ctx.uid,
                "name": ctx.name,
                "digest": atomize_grounding_context_digest(ctx),
            },
            "analysis": {
                "uid": analysis.uid,
                "digest": atomize_grounding_canonical_digest(
                    analysis.to_dict()
                ),
            },
            "workbench": {
                "uid": workbench.uid,
                "digest": atomize_workbench_issue_digest(
                    workbench.issues
                ),
                "response_digest": atomize_workbench_response_digest(
                    workbench
                ),
            },
        }
    )
    session = AtomizeGroundingSession.create(
        bindings=bindings,
        anchor=AtomizeGroundingAnchor.from_dict(
            {
                "issue_uid": anchor_finding.uid,
                "kind": anchor_finding.kind,
                "arity": "UNARY",
                "source_uids": list(anchor_finding.source_uids),
                "issue_digest": atomize_grounding_canonical_digest(
                    {
                        "uid": anchor_finding.uid,
                        "source_uids": list(anchor_finding.source_uids),
                    }
                ),
                "selected_reading_uid": None,
                "selected_reading_text": "",
                "workbench_response": "",
            }
        ),
    )
    session.start_turn(
        "This entrance accepts a physical NFC card only; the app is wrong."
    )
    return ctx, analysis, session, (first.uid, second.uid, third.uid)


def _valid_response(payload: dict) -> dict[str, object]:
    memories = payload["context"]["memories"]
    anchor_id = payload["anchor"]["issue_id"]
    downstream_id = next(
        issue["issue_id"]
        for issue in payload["actionable_issues"]
        if issue["issue_id"] != anchor_id
    )
    current_turn_id = payload["turns"][-1]["turn_id"]
    return {
        "active_understanding": [
            "The Main Building entrance accepts only a physical NFC card.",
            "App guidance is not valid for that entrance.",
        ],
        "answered_prior_question_ids": [],
        "direct": {
            "status": "RESOLVED",
            "explanation": "The latest user assertion selects one credential.",
            "proposal_keys": ["edit-guidance"],
            "question_keys": [],
        },
        "downstream": [
            {
                "issue_id": downstream_id,
                "effect": "REQUIRES_CHANGE",
                "explanation": (
                    "The staff rule needs a stand-alone credential statement."
                ),
                "proposal_keys": ["add-staff-rule"],
                "question_keys": [],
            }
        ],
        "follow_ups": [],
        "edits": [
            {
                "proposal_key": "edit-guidance",
                "necessity": "REQUIRED",
                "target_memory_id": memories[0]["memory_id"],
                "expected_content_digest": memories[0]["content_digest"],
                "content": (
                    "Tell students to use a physical NFC card; do not suggest "
                    "the app."
                ),
                "reason": "The user explicitly rejected app authentication.",
                "issue_ids": [anchor_id],
                "grounded_by_turn_ids": [current_turn_id],
            }
        ],
        "additions": [
            {
                "proposal_key": "add-staff-rule",
                "necessity": "OPTIONAL",
                "content": (
                    "The staff-only entrance also accepts only a physical "
                    "NFC card."
                ),
                "position": len(memories),
                "reason": "This makes the dependent staff rule source-local.",
                "issue_ids": [downstream_id],
                "grounded_by_turn_ids": [current_turn_id],
            }
        ],
        "ready_to_apply": True,
    }


def test_one_call_uses_opaque_ids_preserves_pair_and_never_mutates():
    ctx, analysis, session, source_uids = _fixture()
    provider = FakeProvider(_valid_response)
    context_before = copy.deepcopy(ctx.to_dict())
    session_before = copy.deepcopy(session.to_dict())

    assessment = assess_atomize_grounding_turn(
        ctx,
        analysis,
        session,
        lambda: provider,
    )

    assert len(provider.calls) == 1
    prompt, operation, schema, payload = provider.calls[0]
    assert operation == "atomize_grounding_turn"
    assert schema["additionalProperties"] is False
    assert "untrusted data" in prompt
    assert all(
        source_uid not in prompt
        for source_uid in source_uids
    )
    assert ctx.uid not in prompt
    assert session.uid not in prompt
    assert len(payload["context"]["memories"]) == 3
    meld_contract = payload["meld_contract"]
    assert meld_contract["authority_mode"] == "DIRECTIONAL"
    assert meld_contract["turn_scope"] == "ISSUE"
    assert meld_contract["input_roles"] == ["INCOMING", "BASELINE"]
    assert meld_contract["turn_evidence_role"] == "CLARIFICATION"
    incoming, baseline = meld_contract["frames"]
    assert incoming["frame_id"] == "incoming"
    assert incoming["role"] == "INCOMING"
    assert incoming["kind"] == "ISSUE_CONTEXT"
    assert incoming["persistence"] == "EPHEMERAL"
    assert incoming["context_name"] is None
    assert [
        memory["memory_id"] for memory in incoming["memories"]
    ] == payload["anchor"]["source_memory_ids"]
    assert baseline["frame_id"] == "baseline"
    assert baseline["role"] == "BASELINE"
    assert baseline["kind"] == "CONTAINING_CONTEXT"
    assert baseline["persistence"] == "BOUND"
    assert baseline["context_name"] == ctx.name
    assert [
        memory["memory_id"] for memory in baseline["memories"]
    ] == [
        memory["memory_id"] for memory in payload["context"]["memories"]
    ]
    # Clarification remains one dialogue turn, not a synthetic third frame.
    assert len(meld_contract["frames"]) == 2
    assert payload["turns"][0]["comment"] == session.turns[0].comment
    assert payload["anchor"]["arity"] == "UNARY"
    assert len(payload["turns"]) == 1
    assert payload["previous_assessment"] is None

    assert assessment.direct.status == "RESOLVED"
    assert len(assessment.downstream) == 1
    assert assessment.downstream[0].source_uids == source_uids[1:]
    assert assessment.downstream[0].arity == "PAIR"
    edit, addition = assessment.proposals
    assert edit.operation == "EDIT"
    assert edit.memory_uid == source_uids[0]
    assert edit.expected_content_digest == _digest(
        ctx.memories[source_uids[0]].content
    )
    assert addition.operation == "ADD"
    assert uuid.UUID(addition.memory_uid)
    assert addition.memory_uid not in source_uids
    assert ctx.to_dict() == context_before
    assert session.to_dict() == session_before
    assert session.current_turn is not None
    assert session.current_turn.assessment is None


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda response, payload: response["edits"][0].__setitem__(
                "target_memory_id",
                "m999999",
            ),
            "unknown EDIT target",
        ),
        (
            lambda response, payload: response["edits"][0].__setitem__(
                "expected_content_digest",
                "0" * 64,
            ),
            "stale or invalid EDIT content digest",
        ),
        (
            lambda response, payload: response["downstream"][0].__setitem__(
                "issue_id",
                "i999999",
            ),
            "unknown, duplicate, or anchor downstream issue",
        ),
        (
            lambda response, payload: response["direct"][
                "proposal_keys"
            ].append("invented"),
            "unknown direct proposal",
        ),
    ],
)
def test_unknown_provider_ids_and_stale_edit_digests_fail_closed(
    mutate,
    match,
):
    ctx, analysis, session, _ = _fixture()

    def response(payload):
        value = _valid_response(payload)
        mutate(value, payload)
        return value

    with pytest.raises(AtomizeGroundingProviderError, match=match):
        assess_atomize_grounding_turn(
            ctx,
            analysis,
            session,
            lambda: FakeProvider(response),
        )

    assert session.current_turn is not None
    assert session.current_turn.assessment is None


def test_edit_target_must_be_a_source_of_its_linked_issue():
    ctx, analysis, session, _ = _fixture()

    def response(payload):
        value = _valid_response(payload)
        unrelated = payload["context"]["memories"][2]
        edit = value["edits"][0]
        edit["target_memory_id"] = unrelated["memory_id"]
        edit["expected_content_digest"] = unrelated["content_digest"]
        return value

    with pytest.raises(
        AtomizeGroundingProviderError,
        match="not a source of its linked issue",
    ):
        assess_atomize_grounding_turn(
            ctx,
            analysis,
            session,
            lambda: FakeProvider(response),
        )

    assert session.current_turn is not None
    assert session.current_turn.assessment is None


def test_malformed_output_is_rejected_without_recording_or_mutating():
    ctx, analysis, session, _ = _fixture()
    context_before = copy.deepcopy(ctx.to_dict())
    session_before = copy.deepcopy(session.to_dict())
    provider = FakeProvider(lambda payload: '{"active_understanding": []}')

    with pytest.raises(
        AtomizeGroundingProviderError,
        match="invalid assessment",
    ):
        assess_atomize_grounding_turn(
            ctx,
            analysis,
            session,
            lambda: provider,
        )

    assert len(provider.calls) == 1
    assert ctx.to_dict() == context_before
    assert session.to_dict() == session_before


def test_full_retraction_can_leave_no_active_understanding():
    ctx, analysis, session, _ = _fixture()
    first = session.current_turn
    assert first is not None
    assessment = assess_atomize_grounding_turn(
        ctx,
        analysis,
        session,
        lambda: FakeProvider(_valid_response),
    )
    session.record_assessment(first.uid, assessment)
    retraction = session.start_turn(
        "I retract that clarification without replacing it.",
        revision="RETRACT",
        revises_turn_uids=(first.uid,),
    )

    def empty_understanding(_payload):
        return {
            "active_understanding": [],
            "answered_prior_question_ids": [],
            "direct": {
                "status": "UNRESOLVED",
                "explanation": (
                    "The only credential clarification was retracted."
                ),
                "proposal_keys": [],
                "question_keys": [],
            },
            "downstream": [],
            "follow_ups": [],
            "edits": [],
            "additions": [],
            "ready_to_apply": False,
        }

    result = assess_atomize_grounding_turn(
        ctx,
        analysis,
        session,
        lambda: FakeProvider(empty_understanding),
    )

    assert result.active_understanding == ()
    assert result.direct.status == "UNRESOLVED"
    assert not result.ready_to_apply
    assert retraction.assessment is None


def test_next_turn_payload_carries_cumulative_dialogue_and_prior_assessment():
    ctx, analysis, session, _ = _fixture()
    first = session.current_turn
    assert first is not None
    provider = FakeProvider(_valid_response)
    assessment = assess_atomize_grounding_turn(
        ctx,
        analysis,
        session,
        lambda: provider,
    )
    session.record_assessment(first.uid, assessment)
    second = session.start_turn(
        "Yes, the staff-only entrance uses that same physical-only rule.",
        revision="EXTEND",
    )

    second_provider = FakeProvider(_valid_response)
    assess_atomize_grounding_turn(
        ctx,
        analysis,
        session,
        lambda: second_provider,
    )

    payload = second_provider.calls[0][3]
    assert len(payload["turns"]) == 2
    assert payload["turns"][0]["was_assessed"] is True
    assert payload["turns"][1]["turn_id"] != payload["turns"][0]["turn_id"]
    assert payload["previous_assessment"]["after_turn_id"] == (
        payload["turns"][0]["turn_id"]
    )
    assert payload["previous_assessment"]["direct"]["status"] == "RESOLVED"
    assert second.assessment is None
