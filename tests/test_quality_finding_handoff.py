"""Adapter-neutral quality-finding handoff contracts."""

from __future__ import annotations

import json

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.reviewing.memory_issue_finding.model import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.workbench import (
    QualityFindSourceFrame,
    create_quality_find_workbench,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.handoff import (
    QualityFindingHandoffError,
    conflict_handoff_to_resolve_request,
    quality_finding_handoff_from_json,
    quality_finding_handoff_json,
    quality_finding_handoff,
    quality_finding_handoffs,
)
from memcommit.application.operations.resolve.application import ResolveError
from memcommit.application.operations.review.model import direct_context_digest


def _context():
    context = ops.init("quality/source")
    first = ops.add(context, "The main entrance opens at 8:00.")
    second = ops.add(context, "The main entrance remains closed until 9:00.")
    return context, first, second


def _conflict_session():
    context, first, second = _context()
    report = ConflictReport(
        memory_count=2,
        pair_count=1,
        findings=(
            ConflictFinding(
                left=first,
                right=second,
                conflict="YES",
                reason="Both Memories govern the same entrance at overlapping times.",
                question="Which opening time is authoritative?",
            ),
        ),
    )
    return (
        context,
        first,
        second,
        create_quality_find_workbench(
            "conflicts",
            context,
            report,
        ),
    )


def test_quality_finders_share_one_typed_route_contract():
    context, first, second = _context()
    sessions = (
        create_quality_find_workbench(
            "duplicates",
            context,
            DuplicateReport(
                memory_count=2,
                findings=(
                    DuplicateFinding(
                        first,
                        second,
                        "SEMANTIC_EQUIVALENT",
                        "The claims are substitutable.",
                    ),
                ),
            ),
        ),
        create_quality_find_workbench(
            "ambiguities",
            context,
            AmbiguityReport(
                memory_count=2,
                findings=(
                    AmbiguityFinding(
                        first,
                        "DOMINANT",
                        "REQUIRED",
                        (
                            "The public entrance opens at 8:00.",
                            "The staff entrance opens at 8:00.",
                        ),
                        "The audience is unspecified.",
                        "Does this apply to the public or staff entrance?",
                    ),
                ),
            ),
        ),
        _conflict_session()[3],
    )

    handoffs = tuple(quality_finding_handoffs(session)[0] for session in sessions)

    assert [(handoff.kind, handoff.route) for handoff in handoffs] == [
        ("DUPLICATE", "DEDUP"),
        ("AMBIGUITY", "CLARIFY"),
        ("CONFLICT", "RESOLVE"),
    ]
    assert handoffs[1].proposed_readings == (
        "The public entrance opens at 8:00.",
        "The staff entrance opens at 8:00.",
    )
    assert handoffs[2].qualifiers == ()
    assert handoffs[2].sources[0].direct_memory_digest == direct_context_digest(
        sessions[2].source.contexts[0]
    )


def test_conflict_handoff_builds_exact_resolve_request_without_promoting_draft():
    context, first, second, session = _conflict_session()
    finding_uid = f"conflict:{first.uid}:{second.uid}"
    response = session.response_for(finding_uid)
    response.text = "The 8:00 statement should win."

    handoff = quality_finding_handoff(session, finding_uid)
    request = conflict_handoff_to_resolve_request(
        handoff,
        allow_create=True,
    )

    assert handoff.review_draft.text == "The 8:00 statement should win."
    assert request.context_name == context.name
    assert request.memory_selectors == (first.uid, second.uid)
    assert request.requested_effects == ("UPDATE", "CREATE")
    assert request.guidance == ""
    assert request.source_precondition is not None
    assert request.source_precondition.context_uid == context.uid
    assert request.source_precondition.display_name == context.name
    assert request.source_precondition.direct_memory_digest == direct_context_digest(
        context
    )


def test_conflict_handoff_requires_explicit_delete_guidance():
    handoff = quality_finding_handoffs(_conflict_session()[3])[0]

    with pytest.raises(ResolveError, match="guidance"):
        conflict_handoff_to_resolve_request(handoff, allow_delete=True)

    request = conflict_handoff_to_resolve_request(
        handoff,
        allow_delete=True,
        guidance="The obsolete schedule may be retired.",
    )
    assert request.requested_effects == ("UPDATE", "CREATE", "DELETE")


def test_cross_context_conflict_does_not_silently_enter_resolve_v1():
    left = ops.init("quality/left")
    right = ops.init("quality/right")
    ops.add(left, "The entrance opens at 8:00.")
    ops.add(right, "The entrance remains closed until 9:00.")
    source = QualityFindSourceFrame.create(
        (left, right),
        selection_mode="MULTIPLE",
    )
    memories = tuple(source.analysis_context().iter_items())
    session = create_quality_find_workbench(
        "conflicts",
        source,
        ConflictReport(
            memory_count=2,
            pair_count=1,
            findings=(
                ConflictFinding(
                    memories[0],
                    memories[1],
                    "YES",
                    "The opening states conflict.",
                    "Which schedule applies?",
                ),
            ),
        ),
    )

    with pytest.raises(QualityFindingHandoffError, match="one exact Context"):
        conflict_handoff_to_resolve_request(quality_finding_handoffs(session)[0])


def test_handoff_fails_closed_when_finder_source_changed():
    _context_value, first, _second, session = _conflict_session()
    first.content = "Changed after the conflict analysis."

    with pytest.raises(QualityFindingHandoffError, match="changed after analysis"):
        quality_finding_handoffs(session)


def test_handoff_json_round_trip_and_identity_tamper_detection():
    handoff = quality_finding_handoffs(_conflict_session()[3])[0]

    restored = quality_finding_handoff_from_json(quality_finding_handoff_json(handoff))
    assert restored == handoff

    tampered = handoff.to_dict()
    tampered["classification"] = "MAY"
    with pytest.raises(QualityFindingHandoffError, match="identity"):
        quality_finding_handoff_from_json(json.dumps(tampered))

    retargeted = handoff.to_dict()
    retargeted["sources"][0]["context_uid"] = "another-context-uid"
    with pytest.raises(QualityFindingHandoffError, match="identity"):
        quality_finding_handoff_from_json(json.dumps(retargeted))
