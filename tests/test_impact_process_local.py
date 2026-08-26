"""Process-local Forget, Distill, and Resolve Impact projections."""

from __future__ import annotations

import json

import pytest
import typer
from typer.testing import CliRunner

import memcommit.commands.impact.process_local as process_local_command
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.impact.process_local import (
    distill_impact_presentation,
    forget_impact_presentation,
    resolve_impact_presentation,
)
from memcommit.commands.impact.registry import IMPACT_ROUTES
from memcommit.commands.impact.sessions import render_impact_session_snapshot
from memcommit.context import Context, Memory
from memcommit.distill import (
    DISTILL_OPERATION,
    DISTILL_PAYLOAD_MARKER,
    DistillAnalysis,
    DistilledRule,
)
from memcommit.operations.distill.application import DistillResult
from memcommit.distill_goal_fit import DistillGoalFit
from memcommit.operations.fit.judgment import FitAssessment
from memcommit.operations.forget.application import (
    ForgetAnalysisRequest,
    FrozenForgetSource,
    run_forget_analysis,
)
from memcommit.operations.resolve.application import (
    FrozenResolveFrame,
    ResolveAnalysis,
    ResolveCandidate,
    ResolveCost,
    ResolveEffect,
    ResolveFrameMemory,
    ResolveIssue,
    ResolveRequest,
)
from memcommit.summarize import collect_summary_frame
from memcommit.operations.summarize.application import FrozenSummarySource
from memcommit.store import MemoryStore, context_record_digest
from tests.distill_goal_fit_support import passing_distill_goal_fit_response


runner = CliRunner(mix_stderr=False)


class _ForgetPort:
    def __init__(self, context: Context) -> None:
        self.source = FrozenForgetSource(
            context=context,
            display_name=context.name,
            granted=False,
            _runtime_token=self,
        )

    def freeze(self, _request):
        return self.source

    def apply(self, *_args, **_kwargs):
        raise AssertionError("Impact must never call Forget Apply.")


class _ForgetProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "forget"
        messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1])
        memories = payload["source"]["memories"]
        return json.dumps(
            {
                "overview": "The outdated location is removable.",
                "candidates": [
                    {
                        "source_memory_id": memory["item_id"],
                        "decision": "DELETE" if index == 0 else "KEEP",
                        "proposed_content": "" if index == 0 else memory["content"],
                        "rationale": "Compared with the complete instruction.",
                        "criterion_item_ids": ["k1"],
                    }
                    for index, memory in enumerate(memories)
                ],
            }
        )


class _DistillProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_distill_goal_fit_response(prompt, operation)
        if validation is not None:
            return validation
        assert operation == DISTILL_OPERATION
        payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
        aliases = [memory["memory_id"] for memory in payload["source"]["memories"]]
        return json.dumps(
            {
                "overview": "The evidence supports one bounded preference.",
                "rules": [
                    {
                        "content": "Prefer a quiet setting for conversation.",
                        "rationale": "The quiet example directly supports it.",
                        "support_memory_ids": aliases[:1],
                        "boundary_memory_ids": aliases[1:2],
                    }
                ],
                "outside_memory_ids": aliases[2:],
            }
        )


class _ResolveProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "fit_propositions":
            payload = json.loads(prompt.split("FIT PROPOSITION PAYLOAD:\n", 1)[1])
            judgments = []
            for question in payload["questions"]:
                aliases = [
                    item["proposition_id"]
                    for item in (*question["background"], *question["propositions"])
                ]
                initial = question["question_id"] == "resolve-initial"
                judgments.append(
                    {
                        "question_id": question["question_id"],
                        "verdict": "NO" if initial else "YES",
                        "reason": (
                            "The original times conflict."
                            if initial
                            else "The revised frame is compatible."
                        ),
                        "considered_proposition_ids": aliases,
                        "material_proposition_ids": aliases if initial else [],
                        "consistent_reading": "",
                        "inconsistent_reading": "",
                    }
                )
            return json.dumps(
                {"overview": "Complete Fit coverage.", "judgments": judgments}
            )
        if operation == "resolve_candidates":
            return json.dumps(
                {
                    "question": "Which schedule scope should be authoritative?",
                    "candidates": [
                        {
                            "summary": "Scope the second schedule.",
                            "classification": "EXACT_GROUNDING",
                            "resolution_level": "YES",
                            "rule_ids": ["R04_EXACT_GROUNDING"],
                            "issues": [
                                {
                                    "issue_id": "schedule-scope",
                                    "kind": "TEMPORAL",
                                    "memory_ids": ["m1", "m2"],
                                    "selected_interpretation": (
                                        "The schedules apply on different days."
                                    ),
                                    "basis_ids": ["m1", "m2"],
                                    "assumptions": [],
                                    "reason": "The edit exposes the day scope.",
                                }
                            ],
                            "effects": [
                                {
                                    "kind": "UPDATE",
                                    "target_id": "m2",
                                    "new_content": "The office opens at 9 on weekends.",
                                    "source_ids": ["m1", "m2"],
                                    "reason": "The weekend scope preserves both claims.",
                                }
                            ],
                        }
                    ],
                }
            )
        if operation == "resolve_candidate_verification":
            payload = json.loads(prompt.split("VERIFY PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "reviews": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "grounded": True,
                            "preserves_information": True,
                            "delete_justified": True,
                            "reason": "The candidate uses only cited Source content.",
                        }
                        for candidate in payload["candidates"]
                    ]
                }
            )
        raise AssertionError(operation)


def _forget_result():
    context = Context(
        uid="00000000-0000-4000-8000-000000000001",
        name="impact/forget",
    )
    context.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000011",
            content="The desk used to be beside the west entrance.",
        )
    )
    context.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000012",
            content="Step-free access remains at the north entrance.",
        )
    )
    result = run_forget_analysis(
        ForgetAnalysisRequest(context.name, "Forget the old desk location."),
        source_port=_ForgetPort(context),
        provider_factory=_ForgetProvider,
    )
    return context, result


def _distill_result() -> DistillResult:
    context = Context(
        uid="00000000-0000-4000-8000-000000000101",
        name="impact/distill",
    )
    context.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000111",
            content="A quiet setting supported a long conversation.",
        )
    )
    frame = collect_summary_frame(context)
    analysis = DistillAnalysis(
        uid="00000000-0000-4000-8000-000000000121",
        source=frame,
        goal="Identify a supported conversation preference.",
        overview="The example supports one bounded preference.",
        rules=(
            DistilledRule(
                uid="00000000-0000-4000-8000-000000000131",
                content="Prefer a quiet setting when conversation is the purpose.",
                rationale="The Source example directly supports the condition.",
                support_memory_uids=("00000000-0000-4000-8000-000000000111",),
                boundary_memory_uids=(),
            ),
        ),
        outside_memory_uids=(),
        goal_fit=DistillGoalFit(
            verdict="FIT",
            reason="The proposed Rule is relevant to and compatible with the Goal.",
            considered_rule_uids=(
                "00000000-0000-4000-8000-000000000131",
            ),
            material_rule_uids=(),
        ),
    )
    return DistillResult(
        analysis=analysis,
        frozen_source=FrozenSummarySource(frame=frame, token="test"),
    )


def _resolve_analysis() -> ResolveAnalysis:
    request = ResolveRequest("impact/resolve")
    frame = FrozenResolveFrame(
        request=request,
        context_uid="context-1",
        context_name="impact/resolve",
        display_name="impact/resolve",
        context_digest="digest",
        revision="revision",
        memories=(
            ResolveFrameMemory("m1", "memory-1", "The office opens at 8."),
            ResolveFrameMemory("m2", "memory-2", "The office opens at 9."),
        ),
        actionable_uids=("memory-1", "memory-2"),
        allowed_effects=("UPDATE", "CREATE"),
    )

    def candidate(uid: str, target: str, new_content: str) -> ResolveCandidate:
        return ResolveCandidate(
            uid=uid,
            summary="Scope one schedule statement.",
            classification="EXACT_GROUNDING",
            resolution_level="YES",
            rule_ids=("R04_EXACT_GROUNDING",),
            issues=(
                ResolveIssue(
                    uid="schedule-scope",
                    kind="TEMPORAL",
                    memory_uids=("memory-1", "memory-2"),
                    selected_interpretation=("The schedules apply on different days."),
                    basis_memory_uids=("memory-1", "memory-2"),
                    assumptions=(),
                    reason="The edit exposes the day scope.",
                ),
            ),
            effects=(
                ResolveEffect(
                    kind="UPDATE",
                    owner_context_uid=frame.context_uid,
                    owner_context_name=frame.display_name,
                    memory_uid=target,
                    old_content=(
                        "The office opens at 8."
                        if target == "memory-1"
                        else "The office opens at 9."
                    ),
                    new_content=new_content,
                    source_memory_uids=("memory-1", "memory-2"),
                    reason="The explicit day scope makes the frame compatible.",
                ),
            ),
            grounded=True,
            verification_reason="The complete revised frame independently Fits.",
            fit=FitAssessment(
                question_id=f"verify-{uid}",
                verdict="YES",
                reason="The complete revised frame is compatible.",
                considered_proposition_ids=("p1", "p2"),
                material_proposition_ids=(),
            ),
            cost=ResolveCost(deletes=0, creates=0, updates=1, changed_units=1),
        )

    first = candidate(
        "candidate-1",
        "memory-2",
        "The office opens at 9 on weekends.",
    )
    return ResolveAnalysis(
        frame=frame,
        status="PROPOSAL",
        initial_fit=None,
        candidates=(first,),
        question="Use the automatic schedule interpretation?",
    )


def test_process_local_registry_requires_an_exact_handler_set() -> None:
    with pytest.raises(ValueError, match="missing"):
        IMPACT_ROUTES.install(typer.Typer(), {})


def test_forget_impact_projects_complete_in_place_diff_without_applying() -> None:
    source, result = _forget_result()
    before = tuple(memory.content for memory in source.memories.values())

    rendered = render_impact_session_snapshot(forget_impact_presentation(result))

    assert "IMPACT · FORGET · SAME SOURCE" in rendered
    assert "- The desk used to be beside the west entrance." in rendered
    assert "= Step-free access remains at the north entrance." in rendered
    assert "[ APPLY? ]" not in rendered
    assert tuple(memory.content for memory in source.memories.values()) == before


def test_distill_impact_marks_the_result_not_created_and_source_unchanged() -> None:
    rendered = render_impact_session_snapshot(
        distill_impact_presentation(
            _distill_result(),
            save_as="impact/rules",
        )
    )

    assert "RESULT · impact/rules · CREATE ON APPLY" in rendered
    assert "PROPOSED RULES · 1" in rendered
    assert "IMPACT · DISTILL" not in rendered
    assert "[ADD]" not in rendered
    assert "Prefer a quiet setting when conversation is the" in rendered
    assert "purpose." in rendered
    assert "[ APPLY? ]" not in rendered


def test_resolve_impact_projects_one_exact_verified_candidate_diff() -> None:
    rendered = render_impact_session_snapshot(
        resolve_impact_presentation(
            _resolve_analysis(),
            candidate_uid=None,
        )
    )

    assert "IMPACT · RESOLVE · SAME SOURCE" in rendered
    assert "- The office opens at 9." in rendered
    assert "+ The office opens at 9 on weekends." in rendered
    assert "[ APPLY? ]" not in rendered


def test_resolve_impact_projects_the_automatic_plan_without_a_choice_set() -> None:
    rendered = render_impact_session_snapshot(
        resolve_impact_presentation(
            _resolve_analysis(),
            candidate_uid=None,
        )
    )

    assert "IMPACT · RESOLVE · SAME SOURCE" in rendered
    assert "automatic, independently Fit-verified interpretation plan" in rendered
    assert "candidate-1" not in rendered
    assert "candidate-2" not in rendered
    assert "[ APPLY? ]" not in rendered


def test_forget_route_runs_the_owning_analysis_without_a_checkpoint(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = ops.init("impact/forget-cli")
    ops.add(source, "The desk used to be beside the west entrance.")
    ops.add(source, "Step-free access remains at the north entrance.")
    store.save(source)
    before = context_record_digest(store.load_direct(source.name))
    checkpoints = tuple(store.list_checkpoints(source.name))
    monkeypatch.setattr(
        process_local_command,
        "connect_forget_provider",
        _ForgetProvider,
    )

    result = runner.invoke(
        app,
        [
            "impact",
            "forget",
            "Forget the old desk location.",
            "--context",
            source.name,
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "IMPACT · FORGET · SAME SOURCE" in result.output
    assert context_record_digest(store.load_direct(source.name)) == before
    assert tuple(store.list_checkpoints(source.name)) == checkpoints


def test_distill_route_leaves_the_proposed_result_uncreated(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = ops.init("impact/distill-cli")
    ops.add(source, "A quiet setting supported a long conversation.")
    ops.add(source, "A noisy setting made conversation difficult.")
    store.save(source)
    before = context_record_digest(store.load_direct(source.name))
    monkeypatch.setattr(
        process_local_command,
        "connect_semantic_provider",
        _DistillProvider,
    )

    result = runner.invoke(
        app,
        [
            "impact",
            "distill",
            source.name,
            "--save-as",
            "impact/distill-result",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "CREATE ON APPLY" in result.output
    assert "PROPOSED RULES · 1" in result.output
    assert "IMPACT · DISTILL" not in result.output
    assert not store.context_exists("impact/distill-result")
    assert context_record_digest(store.load_direct(source.name)) == before


def test_resolve_route_projects_verified_effects_without_applying(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    source = ops.init("impact/resolve-cli")
    ops.add(source, "The office opens at 8.")
    ops.add(source, "The office opens at 9.")
    store.save(source)
    before = context_record_digest(store.load_direct(source.name))
    checkpoints = tuple(store.list_checkpoints(source.name))
    provider = _ResolveProvider()
    monkeypatch.setattr(
        process_local_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["impact", "resolve", "--context", source.name],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "IMPACT · RESOLVE · SAME SOURCE" in result.output
    assert "The office opens at 9 on weekends." in result.output
    assert context_record_digest(store.load_direct(source.name)) == before
    assert tuple(store.list_checkpoints(source.name)) == checkpoints


@pytest.mark.parametrize("operation", ("forget", "distill", "resolve"))
def test_new_impact_routes_are_callable_not_enum_rejections(
    isolated_store,
    operation,
) -> None:
    result = runner.invoke(app, ["impact", operation])

    assert result.exit_code == 1
    assert "Invalid value" not in result.stderr
    assert f"Impact {operation} error:" in result.stderr
