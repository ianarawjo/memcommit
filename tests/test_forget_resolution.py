import json
import uuid

import pytest

import memcommit.ops as ops
from memcommit.commands import forget as forget_command
from memcommit.commands.resolution_workbench_shell import (
    resolution_viewer_fragments,
    session_review_action_view,
    session_todo_view,
)
from memcommit.context import Context, Memory
from memcommit.forget_resolution_adapter import ForgetResolutionWorkbenchAdapter
from memcommit.forget_review import ForgetReview
from memcommit.resolution_workbench import ResolutionNavigation, ResolutionWorkbenchAction
from memcommit.semantic.changes import EditChange, RemoveChange


class BatchForgetLLM:
    model = "test-model"

    def __init__(self, *, omit_last: bool = False):
        self.omit_last = omit_last
        self.payload = None

    def chat(self, messages):
        payload = json.loads(messages[-1]["content"].split("FORGET PAYLOAD:\n", 1)[1])
        self.payload = payload
        records = []
        for index, source in enumerate(payload["source"]["memories"]):
            if index == 0:
                decision, content = "EDIT", "Keep the independent remainder."
            elif index == 1:
                decision, content = "DELETE", ""
            else:
                decision, content = "KEEP", source["content"]
            records.append(
                {
                    "source_memory_id": source["item_id"],
                    "decision": decision,
                    "proposed_content": content,
                    "rationale": "Compared with the complete instruction.",
                    "criterion_item_ids": ["k1"],
                }
            )
        if self.omit_last:
            records.pop()
        return json.dumps({"overview": "Reviewed the whole Source.", "candidates": records})


def _context():
    context = Context(uid=str(uuid.uuid4()), name="personal")
    for content in (
        "Forget this part, but keep the independent remainder.",
        "Forget all of this.",
        "Keep this unrelated Memory.",
    ):
        context.add(Memory(uid=str(uuid.uuid4()), content=content))
    return context


def test_forget_uses_one_complete_batch_but_preserves_sparse_public_changes_api():
    context = _context()
    llm = BatchForgetLLM()

    analysis, _history = ops.analyze_forget(context, "Forget the covered details.", llm)
    changes, _history = ops.forget(context, "Forget the covered details.", BatchForgetLLM())

    assert len(analysis.decisions) == 3
    assert [decision.action for decision in analysis.decisions] == [
        "TRANSFORM",
        "DROP",
        "KEEP",
    ]
    assert [type(change) for change in changes] == [EditChange, RemoveChange]
    assert llm.payload["criteria"]["kind"] == "INSTRUCTION"
    assert len(llm.payload["source"]["memories"]) == 3


def test_forget_batch_fails_closed_when_one_source_decision_is_missing():
    with pytest.raises(ValueError, match="cover every Source"):
        ops.analyze_forget(
            _context(),
            "Forget the covered details.",
            BatchForgetLLM(omit_last=True),
        )


def test_forget_projects_instruction_and_memories_into_shared_resolution_report():
    context = _context()
    instruction = "Forget the covered details."
    analysis, _history = ops.analyze_forget(context, instruction, BatchForgetLLM())
    review = ForgetReview.create(context, instruction, analysis)
    view = ForgetResolutionWorkbenchAdapter(review).view()
    item = view.items[0]

    assert view.route == "SOURCE personal × INSTRUCTION → SAME SOURCE"
    assert [option.label for option in item.options] == [
        "Use recommendation · EDIT",
        "Keep as written",
        "Delete",
    ]
    evidence = item.issue_presentation.evidence[0]
    assert evidence.criterion_blocks[0].heading == "FORGET INSTRUCTION"
    assert evidence.criterion_blocks[0].text == instruction
    assert evidence.sources[0].content == review.candidates[0].source.content

    navigation = ResolutionNavigation(
        selected_item_uid=item.uid,
        expanded_item_uid=item.uid,
    )
    detail = "".join(
        text for _style, text in resolution_viewer_fragments(view, navigation)
    )
    positions = [
        detail.index(heading)
        for heading in (
            "CLASSIFICATION",
            "FORGET INSTRUCTION",
            "SOURCE MEMORY",
            "WHY THIS ACTION",
            "FORGET QUESTION",
            "PROPOSED MEMORY TREATMENTS",
            "PROPOSED RESULT",
            "RESPONSE",
        )
    ]
    assert positions == sorted(positions)


def test_forget_review_materializes_only_reviewed_operation_specific_changes():
    context = _context()
    analysis, _history = ops.analyze_forget(
        context,
        "Forget the covered details.",
        BatchForgetLLM(),
    )
    review = ForgetReview.create(context, "Forget the covered details.", analysis)
    keep_delete_candidate = review.candidates[1]
    review = review.select(keep_delete_candidate.uid, "KEEP")
    custom_candidate = review.candidates[2]
    review = review.select(custom_candidate.uid, "CUSTOM", "Custom retained wording.")

    view = ForgetResolutionWorkbenchAdapter(review).view()
    custom_item = view.item(custom_candidate.uid)
    todo = session_todo_view(
        view,
        {},
        review_and_apply=True,
        read_only=False,
    )

    changes = review.changes()

    assert custom_item.response_state == "ANSWERED"
    assert custom_item.response_text == "Custom retained wording."
    assert todo.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(view, {}, whole_set_available=True).kind == "APPLY"
    )
    assert [type(change) for change in changes] == [EditChange, EditChange]
    assert changes[-1].new_content == "Custom retained wording."


def test_forget_tty_controller_uses_shared_resolution_actions_before_apply(monkeypatch):
    context = _context()
    first_uid = next(iter(context.memories))
    actions = iter(
        (
            ResolutionWorkbenchAction(
                kind="SUBMIT_ITEM",
                item_uid="placeholder",
                option_uid="placeholder:keep",
            ),
            ResolutionWorkbenchAction(kind="ACCEPT"),
        )
    )

    def choose(view_supplier, **_kwargs):
        action = next(actions)
        if action.kind == "SUBMIT_ITEM":
            candidate_uid = view_supplier().items[0].uid
            return ResolutionWorkbenchAction(
                kind="SUBMIT_ITEM",
                item_uid=candidate_uid,
                option_uid=f"{candidate_uid}:keep",
            )
        return action

    monkeypatch.setattr(
        "memcommit.commands.resolution_workbench_shell.run_resolution_workbench_shell",
        choose,
    )

    changes = forget_command._run_resolution_forget(
        context,
        "Forget the covered details.",
        BatchForgetLLM(),
    )

    assert first_uid not in {change.uid for change in changes}
    assert any(isinstance(change, RemoveChange) for change in changes)
    assert first_uid in context.memories
