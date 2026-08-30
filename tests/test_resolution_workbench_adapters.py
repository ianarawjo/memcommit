"""Pure adapter contracts for the shared resolution workbench."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace

from memcommit.application.operations.atomize.domain import (
    ATOMIZE_RULESET_VERSION,
    AtomizeAnalysisItem,
    AtomizeAnalysisSession,
    AtomizeChild,
    AtomizeOverview,
    AtomizeOverviewSection,
    AtomizeQualityIssue,
    AtomizeReading,
)
from memcommit.application.operations.atomize.resolution_adapter import (
    AtomizeResolutionWorkbenchAdapter,
)
from memcommit.application.operations.atomize.records import (
    create_atomize_review_record,
)
from memcommit.core.context import Context, Memory
from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    resolution_viewer_fragments,
    session_review_action_view,
    session_todo_view,
)
from memcommit.application.operations.meld.model import MeldAssessment, MeldSession
from memcommit.application.operations.meld.resolution_projection import (
    MeldResolutionWorkbenchAdapter,
)
from memcommit.application.capabilities.resolution.workbench import ResolutionNavigation
from memcommit.adapters.console.terminal.components.responses.resolution import (
    response_draft_from_item,
    response_target_from_item,
)
from memcommit.application.operations.update.model import (
    AddOperation,
    ContextFingerprint,
    EditOperation,
    RemoveOperation,
    SourceReference,
    UpdateSession,
)
from memcommit.application.operations.update.resolution_adapter import (
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
    left_support = Memory(
        uid=_uid(),
        content="The south entrance remains staffed during construction.",
    )
    right_support = Memory(
        uid=_uid(),
        content="The north entrance appears on the existing visitor map.",
    )
    left = Context(uid=_uid(), name="participant/updates")
    right = Context(uid=_uid(), name="participant/wiki-guidance")
    target = Context(uid=_uid(), name="participant/merged-guidance")
    left.add(left_memory)
    left.add(left_support)
    right.add(right_memory)
    right.add(right_support)
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
                            "frame_uid": left_frame.uid,
                            "memory_uid": left_support.uid,
                        },
                        {
                            "frame_uid": right_frame.uid,
                            "memory_uid": right_memory.uid,
                        },
                        {
                            "frame_uid": right_frame.uid,
                            "memory_uid": right_support.uid,
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
                            "frame_uid": left_frame.uid,
                            "memory_uid": left_support.uid,
                        },
                        {
                            "frame_uid": right_frame.uid,
                            "memory_uid": right_memory.uid,
                        },
                        {
                            "frame_uid": right_frame.uid,
                            "memory_uid": right_support.uid,
                        },
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
        "participant/updates + participant/wiki-guidance → participant/merged-guidance"
    )
    assert [(location.role, location.name) for location in view.context_locations] == [
        ("SOURCE A", "participant/updates"),
        ("SOURCE B", "participant/wiki-guidance"),
        ("RESULT", "participant/merged-guidance"),
    ]
    assert view.status == "READY_TO_APPLY"
    assert all(item.commentable for item in view.items)
    assert view.overview.startswith(assessment.overview)
    assert "ACCOUNTING" in view.overview
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
    assert item.title == assessment.relations[0].summary
    assert not item.title.lower().startswith("scoped")
    assert item.options[0].uid == option_uid
    assert item.options[0].text == "Replace north with south."
    assert item.issue_presentation is not None
    collision = item.issue_presentation.evidence[0]
    blocks = {block.heading: block.text for block in item.blocks}
    assert collision.group_heading == "SOURCE RELATION · R1"
    assert collision.sources_heading == "SOURCE CLAIMS"
    assert "SCOPED · RESOLVED" in collision.classification
    assert [claim.label for claim in collision.claims] == ["CLAIM 1", "CLAIM 2"]
    assert collision.claims[0].context_name == "participant/updates"
    assert collision.claims[0].sources[0].content == left_memory.content
    assert collision.claims[0].sources[1].content == left_support.content
    assert collision.claims[1].context_name == "participant/wiki-guidance"
    assert collision.claims[1].sources[1].content == right_support.content
    assert collision.reason == assessment.relations[0].reason
    assert item.issue_presentation.prompt_heading == "RESOLUTION QUESTION"
    assert item.issue_presentation.options_heading == "PROPOSED RESOLUTIONS"
    assert assessment.proposals[0].content in blocks["PROPOSED RESULT"]
    assert item.decision_block_index == 0
    assert len(item.evidence_refs) == 4
    assert item.judgment_refs[0].key == relation_uid
    assert item.outcome_refs[0].key == proposal_uid
    rendered = "".join(
        text
        for _style, text in resolution_viewer_fragments(
            view,
            ResolutionNavigation(selected_item_uid=issue_uid),
        )
    )
    assert rendered.index("SOURCE RELATION") < rendered.index("RESOLUTION QUESTION")
    assert rendered.index("CLASSIFICATION") < rendered.index("SOURCE CLAIMS")
    assert rendered.index("SOURCE CLAIMS") < rendered.index("CLAIM 1 · FROM")
    assert rendered.index("CLAIM 2 · FROM") < rendered.index(
        "WHY SCOPE CHANGES THE RELATION"
    )
    assert "CLAIM 1 · FROM participant/updates" in rendered
    assert "CLAIM 2 · FROM participant/wiki-guidance" in rendered
    assert f"[{left_memory.uid[:8]}] {left_memory.content}" in rendered
    assert rendered.count("CLAIM 1 · FROM participant/updates") == 1
    assert f"[{left_support.uid[:8]}] {left_support.content}" in rendered
    assert left_memory.uid not in rendered
    assert "PROPOSED RESOLUTIONS" in rendered
    assert "TRACE" not in rendered
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


def test_atomize_adapter_joins_read_only_findings_and_ignores_legacy_response() -> None:
    analysis, conflict_uid, composite_uid = _atomize_fixture()
    workbench = create_atomize_review_record(analysis)
    response = workbench.response_for(conflict_uid)
    response.selected_choice_uid = "reading:different-doors"
    response.text = "The access rule is for the staff entrance."

    view = AtomizeResolutionWorkbenchAdapter(analysis, workbench).view()

    assert view.list_label == "ATOMIZE FINDINGS"
    assert view.capabilities == frozenset({"ACCEPT"})
    assert view.accept_enabled is True
    assert view.accept_mode == "AS_IS"
    assert view.unresolved_at_apply_count == 1
    assert view.status == "READY_TO_APPLY_AS_IS"
    assert all(not item.commentable for item in view.items)
    assert view.results == ()
    assert [section.heading for section in view.overview_sections] == [
        "UNDERSTOOD",
        "CHANGED",
        "UNRESOLVED",
    ]
    assert [metric.value for metric in view.metrics] == ["2", "3", "2", "1"]
    assert [
        (location.role, location.name, location.state)
        for location in view.context_locations
    ] == [
        ("SOURCE", "participant/construction-updates", ""),
        ("OUTPUT", "participant/construction-updates", "IN PLACE"),
    ]
    conflict = view.item(conflict_uid)
    assert conflict.status == "RECORDED"
    assert conflict.selected_option_uid is None
    assert conflict.question == "Do both rules concern the north door?"
    assert conflict.options == ()
    blocks = {block.heading: block.text for block in conflict.blocks}
    assert conflict.issue_presentation is not None
    evidence = conflict.issue_presentation.evidence[0]
    assert evidence.group_heading == ""
    assert evidence.sources_heading == "SOURCE MEMORIES"
    assert evidence.sources[0].content == "Staff use an NFC card."
    assert "north door closes" in evidence.sources[1].content
    assert analysis.quality_issues[0].reason == evidence.reason
    assert evidence.reason_heading == "WHY THESE MEMORIES CONFLICT"
    assert conflict.issue_presentation.prompt_heading == "RESOLUTION QUESTION"
    assert conflict.issue_presentation.options_heading == "PROPOSED RESOLUTIONS"
    assert "SAVED RESPONSE" not in blocks
    response_target = response_target_from_item(view, conflict, read_only=False)
    assert response_target is None
    response_draft = response_draft_from_item(conflict)
    assert response_draft.selected_choice_uid is None
    assert response_draft.text == ""
    assert conflict.decision_block_index == 0
    assert len(conflict.evidence_refs) == 2
    assert conflict.judgment_refs[0].key == conflict_uid

    rendered = "".join(
        text
        for _style, text in resolution_viewer_fragments(
            view,
            ResolutionNavigation(selected_item_uid=conflict_uid),
            include_response_sections=False,
        )
    )
    assert rendered.index("CLASSIFICATION") < rendered.index("SOURCE 1 · FROM")
    assert rendered.index("CLASSIFICATION") < rendered.index("SOURCE MEMORIES")
    assert rendered.index("SOURCE MEMORIES") < rendered.index("SOURCE 1 · FROM")
    assert rendered.index("SOURCE 2 · FROM") < rendered.index(
        "WHY THESE MEMORIES CONFLICT"
    )
    assert "RESOLUTION QUESTION" not in rendered
    assert "RESPONSE" not in rendered
    assert "POSSIBLE READINGS" in rendered
    assert "TRACE" not in rendered

    split = view.item(f"atomize:{composite_uid}")
    assert split.title == f"[{composite_uid[:8]}] {analysis.items[1].content}"
    assert split.title != "ATOMIZE SPLIT"
    assert split.kind == "ATOMIZE_SPLIT"
    assert split.kind_label == "SUGGESTED SPLIT"
    split_blocks = {block.heading: block for block in split.blocks}
    assert split.issue_presentation is not None
    assert split.issue_presentation.evidence[0].sources
    child_rows = split_blocks["PROPOSED CHILDREN"].memory_rows
    assert [row.ordinal for row in child_rows] == [1, 2]
    assert child_rows[0].content == "The north door closes."
    assert child_rows[1].content == "The south door remains open."
    assert all(row.ref is not None for row in child_rows)

    split_fragments = resolution_viewer_fragments(
        view,
        ResolutionNavigation(selected_item_uid=split.uid),
        include_response_sections=False,
    )
    split_rendered = "".join(text for _style, text in split_fragments)
    assert "atomize-child:" not in split_rendered
    assert any(
        style == "class:memory-object" and "MEMORY 1 · The north door closes." in text
        for style, text in split_fragments
    )


def test_atomize_adapter_legacy_response_does_not_change_structural_apply() -> None:
    analysis, _conflict_uid, _composite_uid = _atomize_fixture()
    reviewed = replace(
        analysis,
        quality_issues=(),
        source_review_uid=_uid(),
        source_review_digest=_digest("reviewed-responses"),
    )
    workbench = create_atomize_review_record(reviewed)

    ready = AtomizeResolutionWorkbenchAdapter(reviewed, workbench).view()

    assert ready.status == "READY_TO_APPLY"
    assert ready.accept_enabled is True
    assert ready.capabilities == frozenset({"ACCEPT"})

    workbench.response_for(workbench.ordered_issues()[0].uid).text = "Revise it."
    edited = AtomizeResolutionWorkbenchAdapter(reviewed, workbench).view()

    assert edited.status == "READY_TO_APPLY"
    assert edited.accept_enabled is True
    assert edited.capabilities == frozenset({"ACCEPT"})
    assert (
        session_review_action_view(
            edited,
            {},
            whole_set_available=True,
        ).kind
        == "APPLY"
    )


def test_applied_atomize_adapter_is_read_only_review_evidence() -> None:
    analysis, _conflict_uid, _composite_uid = _atomize_fixture()
    workbench = create_atomize_review_record(analysis)
    workbench.record_application(
        output_context_name=analysis.context_name,
        checkpoint_uid=_uid(),
    )

    view = AtomizeResolutionWorkbenchAdapter(analysis, workbench).view()

    assert view.status == "APPLIED"
    assert view.capabilities == frozenset()
    assert view.accept_enabled is False
    assert view.unresolved_at_apply_count == 0
    assert view.input_locked is True
    split = next(item for item in view.items if item.kind == "ATOMIZE_SPLIT")
    assert [block.heading for block in split.blocks] == ["APPLIED CHILD MEMORIES"]


def test_unanswered_atomize_quality_finding_advances_to_apply_as_is() -> None:
    analysis, conflict_uid, _composite_uid = _atomize_fixture()
    workbench = create_atomize_review_record(analysis)
    view = AtomizeResolutionWorkbenchAdapter(analysis, workbench).view()

    todo = session_todo_view(
        view,
        {},
        review_and_apply=True,
        read_only=False,
    )

    assert view.item(conflict_uid).priority == "HIGH"
    assert view.item(conflict_uid).effective_obligation == "NONE"
    assert view.accept_enabled is True
    assert view.accept_mode == "AS_IS"
    assert view.unresolved_at_apply_count == 1
    assert view.status == "READY_TO_APPLY_AS_IS"
    assert todo.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(view, {}, whole_set_available=True).kind
        == "APPLY AS IS"
    )
    assert todo.label == "Confirm final Atomize Apply"
    final_action = session_review_action_view(view, {}, whole_set_available=True)
    assert final_action.detail.startswith(
        "1 unresolved finding will be recorded at apply."
    )
    assert final_action.detail.endswith("Recovery: mem undo.")


def test_reviewed_atomize_split_advances_shared_todo_to_apply() -> None:
    analysis, _conflict_uid, _composite_uid = _atomize_fixture()
    reviewed = replace(
        analysis,
        quality_issues=(),
        source_review_uid=_uid(),
        source_review_digest=_digest("reviewed-split"),
    )
    workbench = create_atomize_review_record(reviewed)
    view = AtomizeResolutionWorkbenchAdapter(reviewed, workbench).view()

    todo = session_todo_view(
        view,
        {},
        review_and_apply=True,
        read_only=False,
    )

    assert [item.priority for item in view.items] == ["REVIEW"]
    assert todo.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(view, {}, whole_set_available=True).kind == "APPLY"
    )
    assert todo.label == "Confirm final Atomize Apply"
    assert "APPLY is available" in todo.detail


def test_initial_atomize_optional_split_is_already_ready_to_apply() -> None:
    analysis, _conflict_uid, _composite_uid = _atomize_fixture()
    initial = replace(
        analysis,
        quality_issues=(),
        source_review_uid=None,
        source_review_digest=None,
    )
    workbench = create_atomize_review_record(initial)
    view = AtomizeResolutionWorkbenchAdapter(initial, workbench).view()

    todo = session_todo_view(
        view,
        {},
        review_and_apply=True,
        read_only=False,
    )

    assert view.status == "READY_TO_APPLY"
    assert view.accept_enabled is True
    assert todo.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(view, {}, whole_set_available=True).kind == "APPLY"
    )


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
    assert view.items[1].title == (f"campus-wiki/buildings Memory [{add_uid}]")
    assert not view.items[1].title.startswith("ADD ")
    assert view.report_items_summary is not None
    assert "3 exact target Memory changes" in view.report_items_summary.text
    assert "1 EDIT, 1 ADD, and 1 REMOVE" in view.report_items_summary.text
    assert view.capabilities == frozenset()
    assert view.accept_enabled is False
    assert "unresolved" not in (view.overview + view.empty_message).lower()
    assert [metric.value for metric in view.metrics] == ["1", "1", "1", "3"]
    assert [(location.role, location.name) for location in view.context_locations] == [
        ("SOURCE", "participant/construction-updates"),
        ("TARGET", "campus-wiki"),
    ]

    staged_view = UpdateResolutionWorkbenchAdapter(
        replace(session, status="staged")
    ).view()
    assert staged_view.capabilities == frozenset({"ACCEPT"})
    assert staged_view.accept_enabled is True
    assert all(not item.commentable for item in staged_view.items)
    assert all(item.effective_obligation == "NONE" for item in staged_view.items)

    apply_view = replace(
        view,
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )
    todo = session_todo_view(
        apply_view,
        {},
        review_and_apply=True,
        read_only=False,
    )
    assert todo.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(apply_view, {}, whole_set_available=True).kind
        == "APPLY"
    )
    assert "optional" not in todo.detail.lower()

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
