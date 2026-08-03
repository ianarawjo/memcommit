"""Pure adapter contracts for the shared resolution workbench."""
from __future__ import annotations

import hashlib
import uuid

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
from memcommit.atomize_resolution_adapter import (
    AtomizeResolutionWorkbenchAdapter,
)
from memcommit.atomize_workbench import create_atomize_workbench
from memcommit.context import Context, Memory
from memcommit.meld import MeldAssessment, MeldSession
from memcommit.meld_resolution_adapter import (
    MeldResolutionWorkbenchAdapter,
)
from memcommit.update import (
    AddOperation,
    ContextFingerprint,
    EditOperation,
    RemoveOperation,
    SourceReference,
    UpdateSession,
)
from memcommit.update_resolution_adapter import (
    UpdateResolutionWorkbenchAdapter,
)


def _uid() -> str:
    return str(uuid.uuid4())


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_meld_adapter_preserves_route_issue_evidence_and_exact_proposals() -> None:
    left_memory = Memory(
        uid=_uid(),
        content="Use the south entrance during construction.",
    )
    right_memory = Memory(
        uid=_uid(),
        content="Use the north entrance during construction.",
    )
    left = Context(uid=_uid(), name="participant/updates")
    right = Context(uid=_uid(), name="participant/wiki-guidance")
    target = Context(uid=_uid(), name="participant/merged-guidance")
    left.add(left_memory)
    right.add(right_memory)
    session = MeldSession.create_symmetric(left, right, target)
    turn = session.start_initial_analysis()
    relation_uid = _uid()
    issue_uid = _uid()
    option_uid = _uid()
    proposal_uid = _uid()
    left_frame, right_frame = session.frames
    assessment = MeldAssessment.from_dict(
        {
            "overview": "The entrance notice can be updated without losing scope.",
            "relations": [
                {
                    "uid": relation_uid,
                    "kind": "SCOPED",
                    "status": "RESOLVED",
                    "members": [
                        {
                            "frame_uid": left_frame.uid,
                            "memory_uid": left_memory.uid,
                        },
                        {
                            "frame_uid": right_frame.uid,
                            "memory_uid": right_memory.uid,
                        },
                    ],
                    "summary": "The two notices cover the same construction window.",
                    "reason": "The verified relocation supersedes the old route.",
                }
            ],
            "issues": [
                {
                    "uid": issue_uid,
                    "relation_uids": [relation_uid],
                    "priority": "HELPFUL",
                    "title": "Entrance wording",
                    "question": "Should the notice name the south entrance?",
                    "why_it_matters": "Visitors need one unambiguous route.",
                    "options": [
                        {
                            "uid": option_uid,
                            "label": "Use south entrance",
                            "text": "Replace north with south.",
                        }
                    ],
                }
            ],
            "proposals": [
                {
                    "uid": proposal_uid,
                    "operation": "ADD",
                    "disposition": "SYNTHESIZE",
                    "memory_uid": _uid(),
                    "content": "Use the south entrance during construction.",
                    "reason": "The incoming notice is verified and current.",
                    "relation_uids": [relation_uid],
                    "source_members": [
                        {
                            "frame_uid": left_frame.uid,
                            "memory_uid": left_memory.uid,
                        },
                        {
                            "frame_uid": right_frame.uid,
                            "memory_uid": right_memory.uid,
                        }
                    ],
                    "grounded_by_turn_uids": [],
                }
            ],
            "ready_to_apply": True,
        }
    )
    session.record_assessment(turn.uid, assessment)

    view = MeldResolutionWorkbenchAdapter(session).view()

    assert view.title == "MEM MELD · SYMMETRIC"
    assert view.route == (
        "participant/updates + participant/wiki-guidance → "
        "participant/merged-guidance"
    )
    assert view.status == "READY_TO_APPLY"
    assert view.overview == assessment.overview
    assert view.accept_enabled is True
    assert view.capabilities == frozenset(
        {
            "SUBMIT_ITEM",
            "SUBMIT_ALL",
            "PRESERVE_ALL",
            "DEFER",
            "ACCEPT",
        }
    )
    item = view.item(issue_uid)
    assert item.options[0].uid == option_uid
    assert item.options[0].text == "Replace north with south."
    blocks = {block.heading: block.text for block in item.blocks}
    assert "[PEER] participant/updates" in blocks["SOURCE MEMORIES"]
    assert left_memory.content in blocks["SOURCE MEMORIES"]
    assert "[PEER] participant/wiki-guidance" in blocks["SOURCE MEMORIES"]
    assert "SCOPED · RESOLVED" in blocks["RELATED RELATIONS"]
    assert assessment.relations[0].reason in blocks["RELATED RELATIONS"]
    assert assessment.proposals[0].content in blocks["AFFECTED RESULTS"]
    assert view.results[0].uid == proposal_uid
    assert view.results[0].marker == "+"
    assert view.results[0].label == "SYNTHESIZE"
    assert view.results[0].text == assessment.proposals[0].content


def _atomize_fixture() -> tuple[AtomizeAnalysisSession, str, str]:
    first_uid = _uid()
    second_uid = _uid()
    first = AtomizeAnalysisItem(
        memory_uid=first_uid,
        content="Staff use an NFC card.",
        position=0,
        classification="ATOMIC",
        reason_codes=("A01_ONE_FOCUS",),
        children=(),
        reason="The source has one independently revisable focus.",
        lint=(),
    )
    second = AtomizeAnalysisItem(
        memory_uid=second_uid,
        content="The north door closes, and the south door remains open.",
        position=1,
        classification="COMPOSITE",
        reason_codes=("A01_ONE_FOCUS",),
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
        lint=(),
    )
    conflict_uid = f"conflict:{first_uid}:{second_uid}"
    issue = AtomizeQualityIssue(
        uid=conflict_uid,
        kind="CONFLICT",
        source_uids=(first_uid, second_uid),
        reason="The place scope determines whether both rules concern one door.",
        question="Do both rules concern the north door?",
        conflict="MAY",
        readings=(
            AtomizeReading(
                uid="reading:same-door",
                role="COMPETING",
                label="One door",
                text="Both rules apply to the north door.",
            ),
            AtomizeReading(
                uid="reading:different-doors",
                role="COMPETING",
                label="Different doors",
                text="The access rule applies to another door.",
            ),
        ),
    )
    overview = AtomizeOverview(
        understood=AtomizeOverviewSection(
            text="The sources describe card access and two door states.",
            source_uids=(first_uid, second_uid),
        ),
        changed=AtomizeOverviewSection(
            text="The composite door-state source is split into two children.",
            source_uids=(second_uid,),
        ),
        unresolved=AtomizeOverviewSection(
            text="The possible place conflict still needs reviewer context.",
            source_uids=(first_uid, second_uid),
        ),
    )
    analysis = AtomizeAnalysisSession(
        uid=_uid(),
        created_at="2026-07-31T00:00:00+00:00",
        context_uid=_uid(),
        context_name="participant/construction-updates",
        context_digest=_digest("atomize-context"),
        ruleset_version=ATOMIZE_RULESET_VERSION,
        memory_count=2,
        projected_memory_count=3,
        items=(first, second),
        overview=overview,
        quality_issues=(issue,),
    )
    return analysis, conflict_uid, second_uid


def test_atomize_adapter_joins_findings_sources_children_and_saved_response() -> None:
    analysis, conflict_uid, composite_uid = _atomize_fixture()
    workbench = create_atomize_workbench(analysis)
    response = workbench.response_for(conflict_uid)
    response.selected_choice_uid = "reading:different-doors"
    response.text = "The access rule is for the staff entrance."

    view = AtomizeResolutionWorkbenchAdapter(analysis, workbench).view()

    assert view.list_label == "ACTIONABLE FINDINGS"
    assert view.capabilities == frozenset({"SUBMIT_ITEM"})
    assert view.accept_enabled is False
    assert view.results == ()
    assert [metric.value for metric in view.metrics] == ["2", "3", "2", "1"]
    conflict = view.item(conflict_uid)
    assert conflict.status == "ANSWERED"
    assert conflict.selected_option_uid == "reading:different-doors"
    assert conflict.question == "Do both rules concern the north door?"
    assert [option.uid for option in conflict.options] == [
        "reading:same-door",
        "reading:different-doors",
    ]
    blocks = {block.heading: block.text for block in conflict.blocks}
    assert "SOURCES · PAIR" in blocks
    assert "Staff use an NFC card." in blocks["SOURCES · PAIR"]
    assert "north door closes" in blocks["SOURCES · PAIR"]
    assert analysis.quality_issues[0].reason == blocks["REASON"]
    assert "reading:different-doors" in blocks["SAVED RESPONSE"]
    assert response.text in blocks["SAVED RESPONSE"]

    split = view.item(f"atomize:{composite_uid}")
    split_blocks = {block.heading: block.text for block in split.blocks}
    assert "SOURCES · UNARY" in split_blocks
    assert "The north door closes." in split_blocks["PROPOSED CHILDREN"]
    assert "The south door remains open." in split_blocks["PROPOSED CHILDREN"]


def test_update_adapter_labels_exact_operations_as_noninteractive_changes() -> None:
    source_context_uid = _uid()
    target_context_uid = _uid()
    source_ref = SourceReference(
        context_uid=source_context_uid,
        context_name="participant/construction-updates",
        memory_uid=_uid(),
        content_digest=_digest("verified source"),
    )
    edit_uid = _uid()
    add_uid = _uid()
    remove_uid = _uid()
    edit = EditOperation(
        owner_context_uid=target_context_uid,
        owner_context_name="campus-wiki/buildings",
        memory_uid=edit_uid,
        old_content="The north entrance is open.",
        new_content="The south entrance is open.",
        source_refs=(source_ref,),
        reason="Verified construction access supersedes the old route.",
    )
    addition = AddOperation(
        owner_context_uid=target_context_uid,
        owner_context_name="campus-wiki/buildings",
        memory_uid=add_uid,
        new_content="Temporary accessible parking is in Lot C.",
        source_refs=(source_ref,),
        reason="The verified temporary arrangement needs a new notice.",
    )
    removal = RemoveOperation(
        owner_context_uid=target_context_uid,
        owner_context_name="campus-wiki/buildings",
        memory_uid=remove_uid,
        old_content="The construction shuttle stops at the north entrance.",
        source_refs=(source_ref,),
        reason="The obsolete shuttle stop must be removed.",
    )
    session = UpdateSession(
        uid=_uid(),
        status="impact",
        created_at="2026-07-31T00:00:00+00:00",
        source_uid=source_context_uid,
        source_name="participant/construction-updates",
        source_digest=_digest("source graph"),
        source_contexts=(
            ContextFingerprint(
                uid=source_context_uid,
                name="participant/construction-updates",
                digest=_digest("source graph"),
            ),
        ),
        target_uid=target_context_uid,
        target_name="campus-wiki",
        target_digest=_digest("target graph"),
        target_contexts=(
            ContextFingerprint(
                uid=target_context_uid,
                name="campus-wiki/buildings",
                digest=_digest("target graph"),
            ),
        ),
        operations=(edit, addition, removal),
    )

    view = UpdateResolutionWorkbenchAdapter(session).view()

    assert view.list_label == "PLANNED CHANGES"
    assert [item.kind for item in view.items] == ["EDIT", "ADD", "REMOVE"]
    assert view.capabilities == frozenset()
    assert view.accept_enabled is False
    assert "unresolved" not in (view.overview + view.empty_message).lower()
    assert [metric.value for metric in view.metrics] == ["1", "1", "1", "3"]

    edit_item = view.items[0]
    edit_blocks = {block.heading: block.text for block in edit_item.blocks}
    assert edit_blocks["BEFORE"] == edit.old_content
    assert edit_blocks["AFTER"] == edit.new_content
    assert target_context_uid in edit_blocks["OWNER"]
    assert edit_blocks["REASON"] == edit.reason
    assert source_ref.context_name in edit_blocks["SOURCE REFERENCES"]
    assert source_ref.context_uid in edit_blocks["SOURCE REFERENCES"]
    assert source_ref.memory_uid in edit_blocks["SOURCE REFERENCES"]
    assert source_ref.content_digest in edit_blocks["SOURCE REFERENCES"]

    add_blocks = {block.heading: block.text for block in view.items[1].blocks}
    remove_blocks = {block.heading: block.text for block in view.items[2].blocks}
    assert "BEFORE" not in add_blocks
    assert add_blocks["AFTER"] == addition.new_content
    assert remove_blocks["BEFORE"] == removal.old_content
    assert "AFTER" not in remove_blocks
