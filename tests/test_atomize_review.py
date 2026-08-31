"""Reviewed declared-frame comments for uncertain atomize findings."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.semantic_updates.derive.atomize.domain import (
    AtomizeAnalysisSession,
    AtomizeFrameOrigin,
    AtomizeImpactError,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.application.operations.semantic_updates.derive.atomize.records import (
    AtomizeRecordError,
    AtomizeReviewRecord,
    atomize_review_issue_projection,
    project_atomize_review_findings,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import AutoCheckpoint
from memcommit.persistence.store import MemoryStore


runner = CliRunner()
PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


def _aggregate_response(payload: dict, response: dict) -> dict:
    candidate_ids = [memory["candidate_id"] for memory in payload["memories"]]
    return {
        "overview": {
            "understood": {
                "text": "The test response covers the supplied source Memories.",
                "source_ids": candidate_ids,
            },
            "changed": {
                "text": "The test response records the proposed atomization.",
                "source_ids": candidate_ids,
            },
            "unresolved": {
                "text": "",
                "source_ids": [],
            },
        },
        "items": response["items"],
        "quality_issues": [],
    }


class ReviewedAtomizeProvider:
    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find_duplicates":
            return json.dumps({"findings": []})
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        validating = payload.get("phase") == "normal_form_validation"
        if not validating:
            self.payloads.append(payload)
        memory = payload["memories"][0]
        candidate_id = memory["candidate_id"]
        declared_frame = memory["declared_frame"]
        if validating:
            result = {
                "items": [
                    {
                        "candidate_id": candidate["candidate_id"],
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The result has one independently revisable focus.",
                    }
                    for candidate in payload["memories"]
                ]
            }
        elif declared_frame is None:
            result = {
                "items": [
                    {
                        "candidate_id": candidate_id,
                        "classification": "UNCERTAIN",
                        "reason_codes": ["A06_NO_HIDDEN_CONTEXT"],
                        "children": [],
                        "reason": (
                            "The phrase 'the same NFC' has no declared antecedent."
                        ),
                    }
                ]
            }
        else:
            assert (
                declared_frame == "'the same NFC' means the staff-door NFC credential."
            )
            result = {
                "items": [
                    {
                        "candidate_id": candidate_id,
                        "classification": "COMPOSITE",
                        "reason_codes": [
                            "A01_ONE_FOCUS",
                            "A02_SCOPE_ATTACHED",
                            "A04_SOURCE_GROUNDED",
                        ],
                        "children": [
                            {
                                "content": (
                                    "Staff can enter using the staff-door "
                                    "NFC credential."
                                ),
                                "source_spans": [
                                    "staff can enter",
                                    "staff-door NFC credential",
                                ],
                            },
                            {
                                "content": (
                                    "Students cannot enter using the "
                                    "staff-door NFC credential."
                                ),
                                "source_spans": [
                                    "students cannot enter",
                                    "staff-door NFC credential",
                                ],
                            },
                        ],
                        "reason": (
                            "The declared antecedent fixes the shared "
                            "credential while the source supplies two "
                            "independently revisable access claims."
                        ),
                    }
                ]
            }
        return json.dumps(_aggregate_response(payload, result))


class AllAtomicProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find_duplicates":
            return json.dumps({"findings": []})
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        return json.dumps(
            _aggregate_response(
                payload,
                {
                    "items": [
                        {
                            "candidate_id": memory["candidate_id"],
                            "classification": "ATOMIC",
                            "reason_codes": ["A01_ONE_FOCUS"],
                            "children": [],
                            "reason": "The Memory has one independently revisable focus.",
                        }
                        for memory in payload["memories"]
                    ]
                },
            )
        )


def _init_uncertain_context(store: MemoryStore):
    ctx = ops.init("atomize/reviewed")
    memory = ops.add(
        ctx,
        "The same NFC is used: staff can enter, but students cannot enter.",
    )
    store.save(
        ctx,
        AutoCheckpoint(
            command="init",
            args={"name": ctx.name},
            description=f"Initialized context '{ctx.name}'",
        ),
    )
    store.set_current(ctx.name)
    return ctx, memory


def _stage_operation_response(
    store: MemoryStore,
    analysis: AtomizeAnalysisSession,
    memory_uid: str,
    text: str,
) -> AtomizeReviewRecord:
    """Stage one Atomize-owned execution decision without using Review."""

    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    finding = next(
        item
        for item in project_atomize_review_findings(analysis)
        if memory_uid in item.source_uids
    )
    workbench.response_for(finding.uid).text = text
    store.save_atomize_workbench(workbench)
    return workbench


def test_atomize_findings_are_read_only_until_apply_completes(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _memory = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.semantic_updates.derive.atomize.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.semantic_updates.derive.atomize.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    preview = runner.invoke(app, ["impact", "atomize"])
    incomplete = runner.invoke(app, ["review", "atomize", "--snapshot"])
    applied = runner.invoke(app, ["atomize"])
    review = runner.invoke(app, ["review", "atomize", "--snapshot"])

    assert preview.exit_code == 0, preview.output
    assert "ATOMIZE FINDINGS" in preview.output
    assert "AMBIGUITY" in preview.output
    assert "RESPONSES" not in preview.output
    assert incomplete.exit_code == 1
    assert "execution is not complete" in incomplete.output
    assert applied.exit_code == 0, applied.output
    assert "UNRESOLVED ISSUES · 1 · APPLIED AS-IS" in applied.output
    assert review.exit_code == 0, review.output
    assert "APPLIED ANALYSIS" in review.output
    assert "RESPONSES" not in review.output
    assert len(provider.payloads) == 1


def test_reviewed_frame_may_not_replace_source_memory_evidence():
    ctx = ops.init("frame-only")
    ops.add(ctx, "The same credential is used.")
    declared = {
        next(iter(ctx.memories)): (
            "Staff enter. Students cannot enter. The credential is NFC."
        )
    }

    def respond(payload):
        candidate_id = payload["memories"][0]["candidate_id"]
        return json.dumps(
            _aggregate_response(
                payload,
                {
                    "items": [
                        {
                            "candidate_id": candidate_id,
                            "classification": "COMPOSITE",
                            "reason_codes": ["A04_SOURCE_GROUNDED"],
                            "children": [
                                {
                                    "content": "Staff enter.",
                                    "source_spans": ["Staff enter"],
                                },
                                {
                                    "content": "Students cannot enter.",
                                    "source_spans": ["Students cannot enter"],
                                },
                            ],
                            "reason": "The frame alone supplies both claims.",
                        }
                    ]
                },
            )
        )

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
            return respond(payload)

    with pytest.raises(AtomizeImpactError, match="without source Memory"):
        impact_atomize(
            ctx,
            Provider,
            declared_frames=declared,
        )


def test_legacy_atomize_analysis_loads_with_empty_review_provenance(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.semantic_updates.derive.atomize.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    current = store.load_atomize_analysis(ctx.uid)
    assert current is not None
    legacy = current.to_dict()
    legacy["schema_version"] = 1
    legacy["ruleset_version"] = "atomize-v1-draft"
    legacy.pop("declared_frames")
    legacy.pop("source_review_uid")
    legacy.pop("source_review_digest")
    legacy.pop("overview")
    legacy.pop("quality_issues")
    for item in legacy["items"]:
        for child in item["children"]:
            child.pop("frame_spans")

    restored = AtomizeAnalysisSession.from_dict(legacy)

    assert restored.declared_frames == ()
    assert restored.source_review_uid is None
    assert restored.source_review_digest is None
    assert restored.to_dict()["schema_version"] == 4


def test_plain_impact_resumes_without_incorporating_saved_comments(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, memory = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.semantic_updates.derive.atomize.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    source_analysis = store.load_atomize_analysis(store.load_current_direct().uid)
    assert source_analysis is not None
    comment = "'the same NFC' means the staff-door NFC credential."
    workbench = _stage_operation_response(
        store,
        source_analysis,
        memory.uid,
        comment,
    )

    analysis_before = store._atomize_analysis_path(
        store.load_current_direct().uid
    ).read_bytes()
    plain_reanalysis = runner.invoke(app, ["impact", "atomize"])
    resumed_review = runner.invoke(app, ["review", "atomize", "--snapshot"])

    assert plain_reanalysis.exit_code == 0, plain_reanalysis.output
    assert "Resumed saved analysis" in plain_reanalysis.output
    assert resumed_review.exit_code == 1, resumed_review.output
    assert "execution is not complete" in resumed_review.output
    restored = store.load_atomize_workbench(source_analysis)
    assert restored is not None
    assert restored.responses == workbench.responses
    assert (
        store._atomize_analysis_path(store.load_current_direct().uid).read_bytes()
        == analysis_before
    )
    assert len(provider.payloads) == 1


def test_review_and_atomize_schema_versions_reject_booleans(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.semantic_updates.derive.atomize.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    analysis_data = analysis.to_dict()
    analysis_data["schema_version"] = True
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(analysis_data)

    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    workbench_data = workbench.to_dict()
    workbench_data["schema_version"] = True
    with pytest.raises(AtomizeRecordError):
        AtomizeReviewRecord.from_dict(
            workbench_data,
            issues=atomize_review_issue_projection(analysis),
        )


def test_empty_context_rejects_unknown_declared_frame_before_provider_call():
    ctx = ops.init("empty")

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            raise AssertionError("provider must not be called")

    with pytest.raises(AtomizeImpactError, match="declared frame"):
        impact_atomize(
            ctx,
            Provider,
            declared_frames={"not-a-memory": "context"},
        )


def test_create_analysis_rejects_malformed_declared_frame_origin_cleanly():
    ctx = ops.init("malformed-frame-origin")
    memory = ops.add(ctx, "Use the same credential.")
    provider = ReviewedAtomizeProvider()
    report = impact_atomize(ctx, lambda: provider)

    with pytest.raises(AtomizeImpactError, match="review declaration"):
        create_atomize_analysis(
            ctx,
            report,
            declared_frames={memory.uid: "It refers to the staff credential."},
            declared_frame_origins={
                memory.uid: AtomizeFrameOrigin(
                    review_item_uid=memory.uid,
                    source_analysis_uid=("10000000-0000-4000-8000-000000000001"),
                    uncertainty_reason=None,  # type: ignore[arg-type]
                )
            },
            source_review_uid="20000000-0000-4000-8000-000000000002",
            source_review_digest="0" * 64,
        )


def test_resuming_atomize_review_reports_a_malformed_analysis_cleanly(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.semantic_updates.derive.atomize.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    store._atomize_analysis_path(ctx.uid).write_text(
        "{invalid",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["review", "--snapshot"])

    assert result.exit_code == 1
    assert "Review error: Saved atomize analysis is invalid." in result.output
    assert result.exception is not None
    assert not isinstance(result.exception, ValueError)


def test_atomize_analysis_rejects_forged_frame_content_and_positions(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, _memory = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.semantic_updates.derive.atomize.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    analysis = store.load_atomize_analysis(store.load_current_direct().uid)
    assert analysis is not None

    forged_content = analysis.to_dict()
    forged_content["items"][0]["content"] = "forged content"
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(forged_content)

    forged_position = analysis.to_dict()
    forged_position["items"][0]["position"] = 1
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(forged_position)

    forged_legacy_schema = analysis.to_dict()
    forged_legacy_schema["schema_version"] = 1
    forged_legacy_schema.pop("declared_frames")
    forged_legacy_schema.pop("source_review_uid")
    forged_legacy_schema.pop("source_review_digest")
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(forged_legacy_schema)
