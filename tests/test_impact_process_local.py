"""Process-local Forget, Distill, and Resolve Impact projections."""

from __future__ import annotations

import json

import pytest
import typer
from typer.testing import CliRunner

import memcommit.adapters.console.commands.distill.impact as distill_impact
import memcommit.adapters.console.commands.forget.impact as forget_impact
import memcommit.adapters.console.commands.resolve.impact as resolve_impact
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.impact.process_local import (
    distill_impact_presentation,
    forget_impact_presentation,
    resolve_impact_presentation,
)
from memcommit.adapters.console.commands.impact.registry import (
    install_impact_routes,
)
from memcommit.adapters.console.commands.impact.sessions import render_impact_session_snapshot
from memcommit.core.context import Context, Memory
from memcommit.application.operations.distill.model import (
    DISTILL_OPERATION,
    DISTILL_PAYLOAD_MARKER,
    DistillAnalysis,
    DistilledRule,
)
from memcommit.application.operations.distill.application import DistillResult
from memcommit.application.operations.distill.goal_fit import DistillGoalFit
from memcommit.application.operations.forget.application import (
    ForgetAnalysisRequest,
    FrozenForgetSource,
    run_forget_analysis,
)
from memcommit.application.operations.resolve.application import (
    FrozenResolveFrame,
    ResolveAnalysis,
    ResolveFrameMemory,
    ResolveIssue,
    ResolveRequest,
)
from memcommit.application.operations.audit.application import create_quality_audit
from memcommit.application.operations.audit.model import (
    QUALITY_AUDIT_RULESETS,
    QualityAuditCheck,
    QualityAuditProvenance,
)
from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateReport,
)
from memcommit.application.operations.summarize.model import collect_summary_frame
from memcommit.application.operations.summarize.application import FrozenSummarySource
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.providers.types import ProviderIdentity
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
    identity = ProviderIdentity(provider="test", model="resolve-model")

    def complete(self, prompt, *, operation, output_schema=None):
        if operation in {"find_duplicates", "find_ambiguities"}:
            return json.dumps({"findings": []})
        if operation == "find_conflicts":
            payload = json.loads(prompt.split("QUALITY FIND PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": payload["pairs"][0]["pair_id"],
                            "conflict": "YES",
                            "reason": "The statements need an explicit day scope.",
                            "question": "Which schedule applies on which day?",
                        }
                    ],
                }
            )
        if operation == "resolve_audit_directions":
            payload = json.loads(prompt.split("RESOLVE AUDIT PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "directions": [
                        {
                            "item_id": item["item_id"],
                            "direction": "The schedules apply on different days.",
                        }
                        for item in payload["audit"]["items"]
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
    context_uid = "00000000-0000-4000-8000-000000000201"
    first_uid = "00000000-0000-4000-8000-000000000211"
    second_uid = "00000000-0000-4000-8000-000000000212"
    context = Context(uid=context_uid, name="impact/resolve")
    first = Memory(uid=first_uid, content="The office opens at 8.")
    second = Memory(uid=second_uid, content="The office opens at 9.")
    context.add(first)
    context.add(second)
    def provenance(kind):
        return QualityAuditProvenance(
            operation=f"find_{kind}",
            provider_called=True,
            identity=ProviderIdentity(provider="test", model="resolve-model"),
        )
    audit = create_quality_audit(
        context,
        (
            QualityAuditCheck(
                "duplicates",
                QUALITY_AUDIT_RULESETS["duplicates"],
                DuplicateReport(memory_count=2, findings=()),
                provenance("duplicates"),
            ),
            QualityAuditCheck(
                "ambiguities",
                QUALITY_AUDIT_RULESETS["ambiguities"],
                AmbiguityReport(memory_count=2, findings=()),
                provenance("ambiguities"),
            ),
            QualityAuditCheck(
                "conflicts",
                QUALITY_AUDIT_RULESETS["conflicts"],
                ConflictReport(
                    memory_count=2,
                    pair_count=1,
                    findings=(
                        ConflictFinding(
                            first,
                            second,
                            "YES",
                            "The statements need an explicit day scope.",
                            "Which schedule applies on which day?",
                        ),
                    ),
                ),
                provenance("conflicts"),
            ),
        ),
    )
    request = ResolveRequest("impact/resolve")
    frame = FrozenResolveFrame(
        request=request,
        context_uid=context_uid,
        context_name="impact/resolve",
        display_name="impact/resolve",
        context_digest="digest",
        revision="revision",
        memories=(
            ResolveFrameMemory("m1", first_uid, first.content),
            ResolveFrameMemory("m2", second_uid, second.content),
        ),
        actionable_uids=(first_uid, second_uid),
        allowed_effects=("UPDATE", "CREATE"),
    )

    return ResolveAnalysis(
        frame=frame,
        status="NEEDS_INPUT",
        audit=audit,
        question="Finalize one decision for every Audit item.",
        issues=(
            ResolveIssue(
                uid="schedule-scope",
                audit_key=f"CONFLICT:{first_uid}:{second_uid}",
                audit_snapshot_digest=audit.snapshot_digest,
                kind="CONFLICT",
                classification="YES",
                memory_uids=(first_uid, second_uid),
                proposed_direction="The schedules apply on different days.",
                reason="The statements need an explicit day scope.",
                question="Which schedule applies on which day?",
            ),
        ),
    )


def test_process_local_registry_requires_an_exact_handler_set() -> None:
    with pytest.raises(ValueError, match="missing"):
        install_impact_routes(typer.Typer(), {})


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


def test_resolve_impact_has_no_effect_plan_before_decisions() -> None:
    rendered = render_impact_session_snapshot(
        resolve_impact_presentation(_resolve_analysis())
    )

    assert "IMPACT · RESOLVE · DECISIONS FIRST" in rendered
    assert "UPDATE PLAN" in rendered
    assert "NOT BUILT" in rendered
    assert "The schedules apply on different days." in rendered
    assert "[ APPLY? ]" not in rendered


def test_resolve_impact_explains_the_decision_first_boundary() -> None:
    rendered = render_impact_session_snapshot(
        resolve_impact_presentation(_resolve_analysis())
    )

    assert "No mutation plan exists before Resolve decisions are finalized." in rendered
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
        forget_impact,
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
        distill_impact,
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


def test_resolve_route_projects_decision_inputs_without_planning_or_applying(
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
        resolve_impact,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["impact", "resolve", "--context", source.name],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "IMPACT · RESOLVE · DECISIONS FIRST" in result.output
    assert "The schedules apply on different days." in result.output
    assert "UPDATE PLAN" in result.output
    assert "NOT BUILT" in result.output
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
