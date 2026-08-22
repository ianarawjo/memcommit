"""Focused contracts for the Atomize semantic-result adapter."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace

import pytest

from memcommit.atomize import (
    ATOMIZE_RULESET_VERSION,
    AtomizeAnalysisItem,
    AtomizeAnalysisSession,
    AtomizeChild,
    AtomizeOverview,
    AtomizeOverviewSection,
    AtomizeQualityIssue,
    AtomizeReading,
)
from memcommit.atomize_result_adapter import (
    AtomizeResultWorkbenchAdapter,
    atomize_result_artifact_digest,
    project_atomize_result,
)
from memcommit.result_workbench import ResultWorkbenchView


ATOMIC_UID = "memory-atomic"
COMPOSITE_UID = "memory-composite"
UNCERTAIN_UID = "memory-uncertain"
NON_PROPOSITIONAL_UID = "memory-non-propositional"


def _context_digest(items: tuple[AtomizeAnalysisItem, ...]) -> str:
    return hashlib.sha256(
        json.dumps(
            [
                {"uid": item.memory_uid, "content": item.content}
                for item in items
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _items() -> tuple[AtomizeAnalysisItem, ...]:
    return (
        AtomizeAnalysisItem(
            memory_uid=ATOMIC_UID,
            content="Staff enter with an NFC card.",
            position=0,
            classification="ATOMIC",
            reason_codes=("A01_ONE_FOCUS",),
            children=(),
            reason="The source has one independently revisable focus.",
            lint=(),
        ),
        AtomizeAnalysisItem(
            memory_uid=COMPOSITE_UID,
            content=(
                "The north door closes, and the south door remains open."
            ),
            position=1,
            classification="COMPOSITE",
            reason_codes=("A01_ONE_FOCUS", "A02_SCOPE_ATTACHED"),
            children=(
                AtomizeChild(
                    content="The north door closes.",
                    source_spans=("The north door closes",),
                ),
                AtomizeChild(
                    content="The south door remains open.",
                    source_spans=("the south door remains open",),
                ),
            ),
            reason="The two door states can be revised independently.",
            lint=("multiple sentence-like commitments",),
        ),
        AtomizeAnalysisItem(
            memory_uid=UNCERTAIN_UID,
            content="Use the same credential.",
            position=2,
            classification="UNCERTAIN",
            reason_codes=("A06_NO_HIDDEN_CONTEXT",),
            children=(),
            reason="The antecedent of “same” is unavailable source-locally.",
            lint=(),
        ),
        AtomizeAnalysisItem(
            memory_uid=NON_PROPOSITIONAL_UID,
            content="ACCESS NOTES",
            position=3,
            classification="NON_PROPOSITIONAL",
            reason_codes=("A07_RETAIN_NON_CLAIMS",),
            children=(),
            reason="The source is a heading rather than a factual claim.",
            lint=(),
        ),
    )


def _quality_issues() -> tuple[AtomizeQualityIssue, ...]:
    return (
        AtomizeQualityIssue(
            uid=f"ambiguity:{UNCERTAIN_UID}",
            kind="AMBIGUITY",
            source_uids=(UNCERTAIN_UID,),
            reason=(
                "“same credential” can refer to the staff card or another "
                "credential."
            ),
            question="Which credential is intended?",
            interpretation="DOMINANT",
            clarification="REQUIRED",
            conflict=None,
            readings=(
                AtomizeReading(
                    uid="reading:staff-card",
                    role="DOMINANT",
                    label="Use the staff card",
                    text="The phrase refers to the staff NFC card.",
                ),
                AtomizeReading(
                    uid="reading:other-card",
                    role="ALTERNATIVE",
                    label="Use another credential",
                    text="The phrase refers to a different credential.",
                ),
            ),
        ),
        AtomizeQualityIssue(
            uid=f"conflict:{ATOMIC_UID}:{COMPOSITE_UID}",
            kind="CONFLICT",
            source_uids=(ATOMIC_UID, COMPOSITE_UID),
            reason=(
                "The place scope determines whether the access and closure "
                "rules concern the same door."
            ),
            question="Do both rules concern the north door?",
            conflict="MAY",
            readings=(
                AtomizeReading(
                    uid="reading:same-door",
                    role="COMPETING",
                    label="Rules concern one door",
                    text="Both rules apply to the north door.",
                ),
                AtomizeReading(
                    uid="reading:different-doors",
                    role="COMPETING",
                    label="Rules concern different doors",
                    text="The access rule applies to another door.",
                ),
            ),
            scope_dimensions=("PLACE",),
        ),
    )


def _overview() -> AtomizeOverview:
    return AtomizeOverview(
        understood=AtomizeOverviewSection(
            text=(
                "The notes describe NFC access, two door states, an "
                "unresolved credential, and a retained heading."
            ),
            source_uids=(
                ATOMIC_UID,
                COMPOSITE_UID,
                UNCERTAIN_UID,
                NON_PROPOSITIONAL_UID,
            ),
        ),
        changed=AtomizeOverviewSection(
            text=(
                "One source is split into two children while the remaining "
                "sources stay directly addressable."
            ),
            source_uids=(
                ATOMIC_UID,
                COMPOSITE_UID,
                UNCERTAIN_UID,
                NON_PROPOSITIONAL_UID,
            ),
        ),
        unresolved=AtomizeOverviewSection(
            text=(
                "The credential antecedent and one possible place conflict "
                "remain unresolved."
            ),
            source_uids=(UNCERTAIN_UID, ATOMIC_UID, COMPOSITE_UID),
        ),
    )


def _session(
    *,
    items: tuple[AtomizeAnalysisItem, ...] | None = None,
    overview: AtomizeOverview | None = None,
    quality_issues: tuple[AtomizeQualityIssue, ...] | None = None,
) -> AtomizeAnalysisSession:
    selected_items = _items() if items is None else items
    return AtomizeAnalysisSession(
        uid=str(uuid.uuid4()),
        created_at="2026-07-29T00:00:00+00:00",
        context_uid="context-task-1",
        context_name="task-1",
        context_digest=_context_digest(selected_items),
        ruleset_version=ATOMIZE_RULESET_VERSION,
        memory_count=len(selected_items),
        projected_memory_count=sum(
            (
                len(item.children)
                if item.classification == "COMPOSITE"
                else 1
            )
            for item in selected_items
        ),
        items=selected_items,
        overview=_overview() if overview is None else overview,
        quality_issues=(
            _quality_issues()
            if quality_issues is None
            else quality_issues
        ),
    )


def test_adapter_projects_local_counts_and_three_separate_sections() -> None:
    adapter = AtomizeResultWorkbenchAdapter(_session())
    view = adapter.view()
    metrics = {metric.key: metric.value for metric in view.metrics}

    assert metrics == {
        "source_memories": 4,
        "projected_memories": 5,
        "proposed_splits": 1,
        "split_children": 2,
        "review_issues": 4,
    }
    assert view.status == "ANALYSIS COMPLETE"
    assert view.understood.state == "PRESENT"
    assert view.understood.text == _overview().understood.text
    assert view.happened.state == "PRESENT"
    assert view.happened.text == _overview().changed.text
    assert view.unresolved.state == "PRESENT"
    assert view.unresolved.text == _overview().unresolved.text
    assert "\n" not in view.unresolved.text


def test_representatives_are_first_validated_outcomes_not_typicality_claims() -> None:
    first_atomic = _items()[0]
    second_atomic = replace(
        first_atomic,
        memory_uid="memory-atomic-later",
        content="Visitors enter with a pass.",
        position=1,
    )
    selected_items = (
        first_atomic,
        second_atomic,
        replace(_items()[1], position=2),
        replace(_items()[3], position=3),
    )
    session = _session(
        items=selected_items,
        overview=AtomizeOverview(
            understood=AtomizeOverviewSection(
                text="The sources describe access and door status.",
                source_uids=tuple(
                    item.memory_uid for item in selected_items
                ),
            ),
            changed=AtomizeOverviewSection(
                text="The validated outcomes retain or split each source.",
                source_uids=tuple(
                    item.memory_uid for item in selected_items
                ),
            ),
            unresolved=AtomizeOverviewSection(text=""),
        ),
        quality_issues=(),
    )

    representatives = [
        case
        for case in project_atomize_result(session).cases
        if case.role == "REPRESENTATIVE"
    ]

    assert [case.title for case in representatives] == [
        "ATOMIC · KEEP",
        "COMPOSITE · SPLIT",
        "NON_PROPOSITIONAL · KEEP_CLASSIFIED",
    ]
    assert ATOMIC_UID in representatives[0].uid
    assert "memory-atomic-later" not in {
        case.uid for case in representatives
    }
    assert all(
        "not a statistical claim of typicality" in case.why_selected
        for case in representatives
    )


def test_representative_detail_preserves_exact_source_judgment_and_children() -> None:
    adapter = AtomizeResultWorkbenchAdapter(_session())
    view = adapter.view()
    case = next(
        case
        for case in view.cases
        if case.uid.startswith("representative:composite:")
    )

    detail = adapter.case_detail(case.uid)
    text = "\n".join(block.text for block in detail.blocks)

    assert _items()[1].content in text
    assert _items()[1].reason in text
    assert "The north door closes." in text
    assert "The south door remains open." in text
    assert "Source spans:\n- The north door closes" in text
    assert len(detail.evidence_refs) == 1
    assert len(detail.judgment_refs) == 1
    assert len(detail.outcome_refs) == 2
    assert view.validate_detail(detail) is detail


def test_boundary_cases_sample_saved_kinds_without_duplicating_sources() -> None:
    session = _session()
    adapter = AtomizeResultWorkbenchAdapter(session)
    boundaries = [
        case for case in adapter.view().cases if case.role == "BOUNDARY"
    ]

    assert {case.uid for case in boundaries} == {
        f"boundary:quality:ambiguity:{UNCERTAIN_UID}",
        (
            "boundary:quality:conflict:"
            f"{ATOMIC_UID}:{COMPOSITE_UID}"
        ),
    }
    assert all(
        (
            "saved quality issue kind" in case.why_selected
            or "UNCERTAIN item" in case.why_selected
        )
        for case in boundaries
    )

    ambiguity = adapter.case_detail(
        f"boundary:quality:ambiguity:{UNCERTAIN_UID}"
    )
    ambiguity_text = "\n".join(block.text for block in ambiguity.blocks)
    assert _items()[2].content in ambiguity_text
    assert _quality_issues()[0].reason in ambiguity_text
    assert "Use the staff card" in ambiguity_text
    assert "The phrase refers to the staff NFC card." in ambiguity_text
    assert ambiguity.outcome_refs == ()
    assert ambiguity.unresolved_refs

    # The same source is already exposed by the selected ambiguity case, so
    # the sampling layer does not repeat it as a second UNCERTAIN row. The
    # complete Atomize issue list remains authoritative below this view.
    assert not any("boundary:uncertain:" in case.uid for case in boundaries)


def test_clean_analysis_has_no_invented_boundary_cases() -> None:
    atomic = (_items()[0],)
    clean_overview = AtomizeOverview(
        understood=AtomizeOverviewSection(
            text="The source describes staff access.",
            source_uids=(ATOMIC_UID,),
        ),
        changed=AtomizeOverviewSection(
            text="The source is kept unchanged.",
            source_uids=(ATOMIC_UID,),
        ),
        unresolved=AtomizeOverviewSection(text=""),
    )
    view = project_atomize_result(
        _session(
            items=atomic,
            overview=clean_overview,
            quality_issues=(),
        )
    )

    assert view.unresolved.state == "NONE_REPORTED"
    assert [case.role for case in view.cases] == ["REPRESENTATIVE"]
    assert not any(case.role == "BOUNDARY" for case in view.cases)


def test_uncertain_item_is_sampled_when_no_quality_case_covers_it() -> None:
    uncertain = (replace(_items()[2], position=0),)
    overview = AtomizeOverview(
        understood=AtomizeOverviewSection(
            text="The source asks to reuse an unspecified credential.",
            source_uids=(UNCERTAIN_UID,),
        ),
        changed=AtomizeOverviewSection(
            text="The source is retained without a guessed split.",
            source_uids=(UNCERTAIN_UID,),
        ),
        unresolved=AtomizeOverviewSection(
            text="The credential antecedent remains unresolved.",
            source_uids=(UNCERTAIN_UID,),
        ),
    )
    adapter = AtomizeResultWorkbenchAdapter(
        _session(
            items=uncertain,
            overview=overview,
            quality_issues=(),
        )
    )

    boundary = next(
        case for case in adapter.view().cases if case.role == "BOUNDARY"
    )
    detail = adapter.case_detail(boundary.uid)

    assert boundary.uid == f"boundary:uncertain:{UNCERTAIN_UID}"
    assert detail.unresolved_refs
    assert detail.outcome_refs == ()
    assert _items()[2].content in "\n".join(
        block.text for block in detail.blocks
    )


def test_non_actionable_saved_ambiguity_is_a_boundary_with_current_outcome() -> None:
    atomic = (_items()[0],)
    issue = AtomizeQualityIssue(
        uid=f"ambiguity:{ATOMIC_UID}",
        kind="AMBIGUITY",
        source_uids=(ATOMIC_UID,),
        reason=(
            "The word card has a dominant access-credential reading and a "
            "harmless secondary reading."
        ),
        question="",
        interpretation="DOMINANT",
        clarification="NONE",
        readings=(
            AtomizeReading(
                uid="reading:access",
                role="DOMINANT",
                label="Access credential",
                text="Card denotes the NFC access credential.",
            ),
            AtomizeReading(
                uid="reading:record",
                role="ALTERNATIVE",
                label="Credential record",
                text="Card denotes the corresponding credential record.",
            ),
        ),
    )
    clean_overview = AtomizeOverview(
        understood=AtomizeOverviewSection(
            text="The source describes staff access.",
            source_uids=(ATOMIC_UID,),
        ),
        changed=AtomizeOverviewSection(
            text="The source is kept unchanged.",
            source_uids=(ATOMIC_UID,),
        ),
        unresolved=AtomizeOverviewSection(text=""),
    )
    adapter = AtomizeResultWorkbenchAdapter(
        _session(
            items=atomic,
            overview=clean_overview,
            quality_issues=(issue,),
        )
    )
    case_uid = f"boundary:quality:ambiguity:{ATOMIC_UID}"
    detail = adapter.case_detail(case_uid)

    assert adapter.view().unresolved.state == "NONE_REPORTED"
    assert detail.outcome_refs
    assert detail.unresolved_refs == ()
    assert "The original Memory is kept unchanged." in detail.blocks[-1].text


def test_legacy_missing_overview_does_not_claim_understanding_or_clean_scan() -> None:
    atomic = (_items()[0],)
    legacy = _session(
        items=atomic,
        overview=AtomizeOverview(
            understood=AtomizeOverviewSection(
                text=(
                    "This legacy analysis did not store a semantic "
                    "comprehension summary; inspect its source-linked items "
                    "below."
                )
            ),
            changed=AtomizeOverviewSection(
                text="It proposed 0 splits into 0 children."
            ),
            unresolved=AtomizeOverviewSection(
                text="No unresolved atomization item was recorded."
            ),
        ),
        quality_issues=(),
    )
    adapter = AtomizeResultWorkbenchAdapter(legacy)
    view = adapter.view()

    assert view.understood.state == "NOT_RECORDED"
    assert view.happened.state == "PRESENT"
    assert "Validated item records keep 1 atomic" in view.happened.text
    assert view.unresolved.state == "NOT_RECORDED"
    assert "complete unresolved-finding scan" in view.unresolved.text
    assert "No unresolved atomization item was recorded" not in (
        view.unresolved.text
    )


def test_artifact_digest_and_case_projection_are_deterministic() -> None:
    session = _session()
    first = AtomizeResultWorkbenchAdapter(session)
    second = AtomizeResultWorkbenchAdapter(session)

    assert atomize_result_artifact_digest(session) == (
        first.view().artifact_digest
    )
    assert first.view() == second.view()
    assert [
        first.case_detail(case.uid)
        for case in first.view().cases
    ] == [
        second.case_detail(case.uid)
        for case in second.view().cases
    ]


def test_adapter_revalidates_the_analysis_before_projection() -> None:
    session = replace(_session(), context_digest="0" * 64)

    with pytest.raises(Exception, match="Invalid saved atomize analysis"):
        AtomizeResultWorkbenchAdapter(session)


def test_projection_returns_the_common_view_type() -> None:
    assert isinstance(project_atomize_result(_session()), ResultWorkbenchView)


def test_adapter_rejects_non_atomize_input() -> None:
    with pytest.raises(TypeError, match="AtomizeAnalysisSession"):
        AtomizeResultWorkbenchAdapter(object())  # type: ignore[arg-type]
