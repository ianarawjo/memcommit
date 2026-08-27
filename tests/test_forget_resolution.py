import json
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.application.ops as ops
from memcommit.adapters.console.commands.forget import command as forget_command
from memcommit.adapters.console.commands.shared.resolution_workbench_shell import (
    resolution_report_fragments,
    resolution_viewer_fragments,
    run_resolution_workbench_shell,
    session_review_action_view,
    session_todo_view,
)
from memcommit.context import Context, Memory
from memcommit.adapters.interfaces.tui.operations.forget.resolution import (
    ForgetResolutionWorkbenchAdapter,
    forget_memory_changes,
)
from memcommit.application.operations.forget.review import ForgetReview
from memcommit.adapters.interfaces.tui.workbenches.impact import ImpactController
from memcommit.providers.types import ProviderIdentity
from memcommit.application.resolution.workbench import ResolutionNavigation, ResolutionWorkbenchAction
from memcommit.application.semantic.selective_curation import CurationAnalysis, CurationDecision
from memcommit.application.semantic.changes import EditChange, RemoveChange
from memcommit.application.reviewing.session_navigation import SessionWorkbenchNavigation


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


class BatchForgetProvider:
    identity = ProviderIdentity(provider="test", model="batch-provider")

    def __init__(self):
        self.operation = None
        self.output_schema = None
        self.messages = None

    def complete(self, prompt, *, operation, output_schema=None):
        self.operation = operation
        self.output_schema = output_schema
        self.messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(
            self.messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
        )
        records = [
            {
                "source_memory_id": source["item_id"],
                "decision": "KEEP",
                "proposed_content": source["content"],
                "rationale": "The instruction does not cover this Memory.",
                "criterion_item_ids": ["k1"],
            }
            for source in payload["source"]["memories"]
        ]
        return json.dumps(
            {"overview": "Reviewed the complete Source.", "candidates": records}
        )


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


def test_forget_uses_configured_completion_contract_and_complete_schema():
    context = _context()
    provider = BatchForgetProvider()

    analysis, history = ops.analyze_forget(
        context,
        "Forget the covered details.",
        provider,
    )

    assert provider.operation == "forget"
    assert provider.output_schema["properties"]["candidates"]["minItems"] == 3
    assert provider.output_schema["properties"]["candidates"]["maxItems"] == 3
    assert provider.output_schema["properties"]["candidates"]["items"][
        "properties"
    ]["decision"]["enum"] == ["KEEP", "EDIT", "DELETE"]
    assert len(analysis.decisions) == 3
    assert history[-1]["role"] == "assistant"


def test_forget_projects_instruction_and_memories_into_shared_resolution_report():
    context = _context()
    instruction = "Forget the covered details."
    analysis, _history = ops.analyze_forget(context, instruction, BatchForgetLLM())
    review = ForgetReview.create(context, instruction, analysis)
    view = ForgetResolutionWorkbenchAdapter(review).view()
    item = view.items[0]

    assert view.route == "SOURCE personal × INSTRUCTION → SAME SOURCE"
    assert item.commentable is True
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


def test_forget_projects_complete_source_as_exact_in_place_memory_changes():
    context = _context()
    analysis, _history = ops.analyze_forget(
        context,
        "Forget the covered details.",
        BatchForgetLLM(),
    )
    review = ForgetReview.create(context, "Forget the covered details.", analysis)

    changes = forget_memory_changes(review)

    assert [(change.marker, change.treatment) for change in changes] == [
        ("~", "TRANSFORM"),
        ("−", "DROP"),
        ("=", "KEEP"),
    ]
    assert all(change.location == context.name for change in changes)
    assert changes[0].before == "Forget this part, but keep the independent remainder."
    assert changes[0].after == "Keep the independent remainder."
    assert changes[1].before == "Forget all of this."
    assert changes[1].after is None
    assert changes[2].before == changes[2].after == "Keep this unrelated Memory."


def test_forget_impact_replaces_generic_results_with_source_aware_diff():
    context = _context()
    analysis, _history = ops.analyze_forget(
        context,
        "Forget the covered details.",
        BatchForgetLLM(),
    )
    review = ForgetReview.create(context, "Forget the covered details.", analysis)
    view = ForgetResolutionWorkbenchAdapter(review).view()
    impact = ImpactController.from_memory_changes(
        operation=view.operation,
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT · PROPOSED SOURCE REVISION",
        summary="Exact frozen Source transitions.",
        changes=forget_memory_changes(review),
    )

    rendered = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            review_and_apply=True,
            impact_controller=impact,
        )
    )

    assert "PROPOSED SOURCE RESULT" not in rendered
    assert "IMPACT · PROPOSED SOURCE REVISION" in rendered
    assert "- Forget this part, but keep the independent remainder." in rendered
    assert "+ Keep the independent remainder." in rendered
    assert "- Forget all of this." in rendered
    assert "= Keep this unrelated Memory." in rendered
    assert "This Source Memory will be removed." not in rendered


def test_large_forget_impact_moves_down_one_source_memory_at_a_time():
    context = Context(uid=str(uuid.uuid4()), name="large-source")
    decisions = []
    source_uids = []
    for index in range(278):
        memory = Memory(
            uid=str(uuid.uuid4()),
            content=f"Frozen Source Memory {index + 1:03d}.",
        )
        context.add(memory)
        source_uids.append(memory.uid)
        decisions.append(
            CurationDecision(
                source_uid=memory.uid,
                action="KEEP",
                variant="KEEP",
                proposed_content=memory.content,
                rationale="The instruction does not cover this Memory.",
                criterion_uids=("k1",),
            )
        )
    review = ForgetReview.create(
        context,
        "Forget nothing in this navigation fixture.",
        CurationAnalysis(
            overview="Reviewed the complete large Source.",
            decisions=tuple(decisions),
        ),
    )
    view = ForgetResolutionWorkbenchAdapter(review).view()
    impact = ImpactController.from_memory_changes(
        operation=view.operation,
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT · PROPOSED SOURCE REVISION",
        summary="Exact frozen Source transitions.",
        changes=forget_memory_changes(review),
    )
    workbench_navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Overview -> review summary -> Impact heading -> first Memory -> second.
        pipe_input.send_text("\x1b[B" * 4 + "q")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            impact_controller=impact,
            workbench_navigation=workbench_navigation,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.section_uid == f"REPORT:IMPACT:{source_uids[1]}"


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
    assert [(location.role, location.name) for location in view.context_locations] == [
        ("SOURCE", context.name)
    ]
    assert todo.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(view, {}, whole_set_available=True).kind == "APPLY"
    )
    assert [type(change) for change in changes] == [EditChange, EditChange]
    assert changes[-1].new_content == "Custom retained wording."


def test_forget_tty_controller_uses_shared_resolution_actions_before_apply(monkeypatch):
    context = _context()
    original_contents = {
        uid: memory.content for uid, memory in context.memories.items()
    }
    first_uid = next(iter(context.memories))
    source_memory_count = len(context.memories)
    progress_events: list[tuple[object, ...]] = []

    def wait(operation, stage, *, total, work):
        progress_events.append(("start", operation, stage, total))
        try:
            return work(object())
        finally:
            progress_events.append(("close",))

    monkeypatch.setattr(forget_command, "run_command_wait", wait)
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

    impact_labels = []
    review_behaviors = []

    def choose(view_or_supplier, **kwargs):
        view = view_or_supplier() if callable(view_or_supplier) else view_or_supplier
        impact = kwargs["impact_controller"].view()
        assert impact.replaces_results is True
        assert impact.revision == view.revision
        impact_labels.append(impact.entries[0].label)
        review_behaviors.append(kwargs["decision_free_behavior"])
        action = next(actions)
        if action.kind == "SUBMIT_ITEM":
            candidate_uid = view.items[0].uid
            return ResolutionWorkbenchAction(
                kind="SUBMIT_ITEM",
                item_uid=candidate_uid,
                option_uid=f"{candidate_uid}:keep",
            )
        return action

    monkeypatch.setattr(
        "memcommit.adapters.interfaces.tui.operations.forget.workbench.run_resolution_workbench_shell",
        choose,
    )

    changes = forget_command._run_resolution_forget(
        context,
        "Forget the covered details.",
        BatchForgetLLM(),
    )

    assert first_uid not in {change.uid for change in changes}
    assert any(isinstance(change, RemoveChange) for change in changes)
    assert {
        uid: memory.content for uid, memory in context.memories.items()
    } == original_contents
    assert impact_labels == ["TRANSFORM", "KEEP"]
    assert review_behaviors == ["AUTO_ACCEPT", "AUTO_ACCEPT"]
    assert progress_events == [
        (
            "start",
            "FORGET",
            f"analyzing {source_memory_count} source memories x 1 instruction",
            1,
        ),
        ("close",),
    ]


def test_granted_forget_requires_review_only_when_it_will_publish_a_change(
    monkeypatch,
):
    observed = []

    def choose(_view, **kwargs):
        observed.append(kwargs["decision_free_behavior"])
        return ResolutionWorkbenchAction(kind="ACCEPT")

    monkeypatch.setattr(
        "memcommit.adapters.interfaces.tui.operations.forget.workbench.run_resolution_workbench_shell",
        choose,
    )
    monkeypatch.setattr(
        forget_command,
        "run_command_wait",
        lambda _operation, _stage, *, work, **_kwargs: work(object()),
    )

    changed = forget_command._run_resolution_forget(
        _context(),
        "Forget the covered details.",
        BatchForgetLLM(),
        mutates_granted_authority=True,
    )
    unchanged = forget_command._run_resolution_forget(
        _context(),
        "Forget nothing.",
        BatchForgetProvider(),
        mutates_granted_authority=True,
    )

    assert changed is not None and len(changed) == 2
    assert unchanged == []
    assert observed == ["FINAL_REVIEW", "AUTO_ACCEPT"]
