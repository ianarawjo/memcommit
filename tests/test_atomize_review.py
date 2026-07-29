"""Reviewed declared-frame comments for uncertain atomize findings."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.atomize import (
    AtomizeAnalysisSession,
    AtomizeFrameOrigin,
    AtomizeImpactError,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.atomize_workbench import (
    AtomizeWorkbenchError,
    AtomizeWorkbenchSession,
    atomize_workbench_issue_projection,
)
from memcommit.cli import app
from memcommit.commands.review_shell import RESPONSE_LABEL
from memcommit.context import AutoCheckpoint, Memory
from memcommit.store import MemoryStore


runner = CliRunner()
PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


def _aggregate_response(payload: dict, response: dict) -> dict:
    candidate_ids = [
        memory["candidate_id"] for memory in payload["memories"]
    ]
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
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        memory = payload["memories"][0]
        candidate_id = memory["candidate_id"]
        declared_frame = memory["declared_frame"]
        if declared_frame is None:
            result = {
                "items": [
                    {
                        "candidate_id": candidate_id,
                        "classification": "UNCERTAIN",
                        "reason_codes": ["A06_NO_HIDDEN_CONTEXT"],
                        "children": [],
                        "reason": (
                            "The phrase 'the same NFC' has no declared "
                            "antecedent."
                        ),
                    }
                ]
            }
        else:
            assert (
                declared_frame
                == "'the same NFC' means the staff-door NFC credential."
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
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        return json.dumps(
            _aggregate_response(payload, {
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
            })
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


def test_atomize_review_comment_is_persisted_reanalyzed_and_applied(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, memory = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    context_before = store._context_file(ctx.name).read_bytes()
    checkpoints_before = store.list_checkpoints(ctx.name)

    preview = runner.invoke(app, ["impact", "atomize"])
    review = runner.invoke(app, ["review", "atomize", "--snapshot"])

    assert preview.exit_code == 0, preview.output
    assert "UNCERTAIN" in preview.output
    assert "ISSUES" in preview.output
    assert "ATOMIZE UNCERTAINTY" in preview.output
    assert review.exit_code == 0, review.output
    assert "ATOMIZE UNCERTAINTY 1/1" in review.output
    assert "UNCERTAIN · REQUIRES CONTEXT" in review.output
    assert RESPONSE_LABEL in review.output
    assert "READING OPTIONS" not in review.output
    assert len(provider.payloads) == 1

    comment = (
        "'the same NFC' means the staff-door NFC credential."
    )
    responded = runner.invoke(
        app,
        [
            "review",
            "--respond-to",
            memory.uid[:8],
            "--response",
            comment,
        ],
    )
    assert responded.exit_code == 0, responded.output
    assert f"> {comment}" in responded.output
    source_analysis = store.load_atomize_analysis(ctx.uid)
    assert source_analysis is not None
    saved_workbench = store.load_atomize_workbench(source_analysis)
    assert saved_workbench is not None
    assert saved_workbench.answered_count == 1

    refused = runner.invoke(app, ["atomize", "--save"])
    assert refused.exit_code == 1
    assert "workbench responses have not been incorporated" in refused.output
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert store.list_checkpoints(ctx.name) == checkpoints_before

    reanalyzed = runner.invoke(
        app,
        ["impact", "atomize", "--with-review"],
    )
    assert reanalyzed.exit_code == 0, reanalyzed.output
    assert "Incorporated 1 reviewed declared frame" in reanalyzed.output
    assert len(provider.payloads) == 2
    assert (
        provider.payloads[-1]["context"]["declared_frame"]
        == "PER_MEMORY_USER_REVIEW"
    )
    assert provider.payloads[-1]["memories"][0]["declared_frame"] == comment
    framed_examples = {
        case["id"]: case
        for case in provider.payloads[-1]["calibration_cases"]
        if case["declared_frame"] is not None
    }
    assert "declared-frame-grounds-shared-scope" in framed_examples
    assert "해당 기간은" in framed_examples[
        "declared-frame-grounds-shared-scope"
    ]["declared_frame"]

    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    assert analysis.source_review_uid == saved_workbench.uid
    assert len(analysis.declared_frames) == 1
    assert analysis.declared_frames[0].text == comment
    assert analysis.declared_frames[0].review_item_uid == (
        f"atomize:{memory.uid}"
    )
    assert analysis.declared_frames[0].source_analysis_uid == (
        source_analysis.uid
    )
    assert analysis.items[0].classification == "COMPOSITE"
    assert analysis.items[0].children[0].source_spans == (
        "staff can enter",
    )
    assert analysis.items[0].children[0].frame_spans == (
        "staff-door NFC credential",
    )

    # Reanalysis creates a fresh workbench for the new immutable analysis.
    # Both entry points resume it without another provider call.
    resumed_review = runner.invoke(app, ["review", "--snapshot"])
    assert resumed_review.exit_code == 0, resumed_review.output
    assert "ATOMIZE SPLIT" in resumed_review.output
    resumed_preview = runner.invoke(app, ["impact", "atomize"])
    assert resumed_preview.exit_code == 0, resumed_preview.output
    assert "Resumed saved analysis" in resumed_preview.output
    assert len(provider.payloads) == 2

    applied = runner.invoke(
        app,
        ["atomize", "--save-as", "atomize/resolved"],
    )
    assert applied.exit_code == 0, applied.output
    assert store.current_context_name() == "atomize/resolved"
    assert store._context_file(ctx.name).read_bytes() == context_before
    resolved = store.load_direct("atomize/resolved")
    assert [
        item.content
        for item in resolved.iter_items()
        if isinstance(item, Memory)
    ] == [
        "Staff can enter using the staff-door NFC credential.",
        "Students cannot enter using the staff-door NFC credential.",
    ]
    checkpoint = store.list_checkpoints("atomize/resolved")[0]
    assert checkpoint["args"]["source_review_uid"] == saved_workbench.uid
    assert checkpoint["args"]["declared_frame_count"] == 1

    # A later preview replaces the latest per-Context analysis. Applied
    # review evidence must therefore remain reconstructible from the
    # checkpoint rather than only from that replaceable preview artifact.
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        AllAtomicProvider,
    )
    later_preview = runner.invoke(
        app,
        ["impact", "atomize", "--refresh"],
    )
    assert later_preview.exit_code == 0, later_preview.output

    trace = runner.invoke(app, ["trace", memory.uid[:8]])
    assert trace.exit_code == 0, trace.output
    assert "Reviewed declared context/comment" in trace.output
    assert comment in trace.output
    assert "Requested because:" in trace.output
    assert "Applied citations for" in trace.output
    assert "Declared-frame spans: staff-door NFC credential" in trace.output

    rationale = runner.invoke(
        app,
        ["rationale", memory.uid[:8], "--recorded-only"],
    )
    assert rationale.exit_code == 0, rationale.output
    assert "Reviewed declared context/comment" in rationale.output
    assert comment in rationale.output
    assert "Requested because:" in rationale.output
    assert "Applied citations for" in rationale.output
    assert "Reviewer response:" not in rationale.output


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
            _aggregate_response(payload, {
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
            })
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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
    assert restored.to_dict()["schema_version"] == 3


def test_atomize_with_review_requires_a_nonempty_comment_without_provider_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    assert runner.invoke(
        app,
        ["review", "atomize", "--snapshot"],
    ).exit_code == 0
    refused = runner.invoke(
        app,
        ["impact", "atomize", "--with-review"],
    )

    assert refused.exit_code == 1
    assert "No current atomize workbench response matches" in refused.output
    assert len(provider.payloads) == 1


def test_plain_impact_resumes_without_incorporating_saved_comments(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, memory = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    assert runner.invoke(
        app,
        ["review", "atomize", "--snapshot"],
    ).exit_code == 0
    assert runner.invoke(
        app,
        [
            "review",
            "--respond-to",
            memory.uid[:8],
            "--response",
            "'the same NFC' means the staff-door NFC credential.",
        ],
    ).exit_code == 0

    analysis_before = store._atomize_analysis_path(
        store.load_current_direct().uid
    ).read_bytes()
    plain_reanalysis = runner.invoke(app, ["impact", "atomize"])
    resumed_review = runner.invoke(app, ["review", "--snapshot"])

    assert plain_reanalysis.exit_code == 0, plain_reanalysis.output
    assert "Resumed saved analysis" in plain_reanalysis.output
    assert resumed_review.exit_code == 0, resumed_review.output
    assert "'the same NFC' means" in resumed_review.output
    assert store._atomize_analysis_path(
        store.load_current_direct().uid
    ).read_bytes() == analysis_before
    assert len(provider.payloads) == 1


def test_review_and_atomize_schema_versions_reject_booleans(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    analysis_data = analysis.to_dict()
    analysis_data["schema_version"] = True
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(analysis_data)

    assert runner.invoke(
        app,
        ["review", "atomize", "--snapshot"],
    ).exit_code == 0
    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    workbench_data = workbench.to_dict()
    workbench_data["schema_version"] = True
    with pytest.raises(AtomizeWorkbenchError):
        AtomizeWorkbenchSession.from_dict(
            workbench_data,
            issues=atomize_workbench_issue_projection(analysis),
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
                    source_analysis_uid=(
                        "10000000-0000-4000-8000-000000000001"
                    ),
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
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    assert runner.invoke(
        app,
        ["review", "atomize", "--snapshot"],
    ).exit_code == 0
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
    _, memory = _init_uncertain_context(store)
    provider = ReviewedAtomizeProvider()
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
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

    assert runner.invoke(
        app,
        ["review", "atomize", "--snapshot"],
    ).exit_code == 0
    assert runner.invoke(
        app,
        [
            "review",
            "--respond-to",
            memory.uid[:8],
            "--response",
            "'the same NFC' means the staff-door NFC credential.",
        ],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["impact", "atomize", "--with-review"],
    ).exit_code == 0
    reviewed = store.load_atomize_analysis(store.load_current_direct().uid)
    assert reviewed is not None
    forged_review_target = reviewed.to_dict()
    forged_review_target["declared_frames"][0]["review_item_uid"] = ""
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(forged_review_target)

    forged_legacy_ruleset = reviewed.to_dict()
    forged_legacy_ruleset["ruleset_version"] = "atomize-v1-draft"
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(forged_legacy_ruleset)

    forged_self_origin = reviewed.to_dict()
    forged_self_origin["declared_frames"][0]["source_analysis_uid"] = (
        reviewed.uid
    )
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(forged_self_origin)

    forged_legacy_schema = analysis.to_dict()
    forged_legacy_schema["schema_version"] = 1
    forged_legacy_schema.pop("declared_frames")
    forged_legacy_schema.pop("source_review_uid")
    forged_legacy_schema.pop("source_review_digest")
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(forged_legacy_schema)


def test_multiple_atomize_comments_share_one_source_analysis_and_stay_per_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("atomize/multiple-comments")
    first = ops.add(ctx, "Use that door for staff.")
    second = ops.add(ctx, "Use that entrance after hours.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="init",
            args={"name": ctx.name},
            description=f"Initialized context '{ctx.name}'",
        ),
    )
    store.set_current(ctx.name)
    calls: list[dict] = []

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
            calls.append(payload)
            reviewed = all(
                memory["declared_frame"] is not None
                for memory in payload["memories"]
            )
            return json.dumps(
                _aggregate_response(payload, {
                    "items": [
                        {
                            "candidate_id": memory["candidate_id"],
                            "classification": (
                                "ATOMIC" if reviewed else "UNCERTAIN"
                            ),
                            "reason_codes": [
                                (
                                    "A01_ONE_FOCUS"
                                    if reviewed
                                    else "A06_NO_HIDDEN_CONTEXT"
                                )
                            ],
                            "children": [],
                            "reason": (
                                "The reviewed frame resolves the referent."
                                if reviewed
                                else "The referent has no declared antecedent."
                            ),
                        }
                        for memory in payload["memories"]
                    ]
                })
            )

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        Provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    source_analysis = store.load_atomize_analysis(ctx.uid)
    assert source_analysis is not None
    assert runner.invoke(
        app,
        ["review", "atomize", "--snapshot"],
    ).exit_code == 0
    comments = {
        first.uid: "'that door' means the staff entrance.",
        second.uid: "'that entrance' means the main entrance.",
    }
    for memory_uid, comment in comments.items():
        result = runner.invoke(
            app,
            [
                "review",
                "--respond-to",
                memory_uid[:8],
                "--response",
                comment,
            ],
        )
        assert result.exit_code == 0, result.output

    reanalyzed = runner.invoke(app, ["impact", "atomize", "--with-review"])
    assert reanalyzed.exit_code == 0, reanalyzed.output
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    assert len(analysis.declared_frames) == 2
    assert {
        frame.memory_uid: frame.text
        for frame in analysis.declared_frames
    } == comments
    assert {
        frame.source_analysis_uid
        for frame in analysis.declared_frames
    } == {source_analysis.uid}

    forged_mixed_origin = analysis.to_dict()
    forged_mixed_origin["declared_frames"][1]["source_analysis_uid"] = (
        "10000000-0000-4000-8000-000000000001"
    )
    with pytest.raises(AtomizeImpactError):
        AtomizeAnalysisSession.from_dict(forged_mixed_origin)

    applied = runner.invoke(app, ["atomize", "--save"])
    assert applied.exit_code == 0, applied.output
    checkpoint = next(
        entry
        for entry in store.list_checkpoints(ctx.name)
        if entry["command"] == "atomize"
    )
    evidence_by_source = {
        change["source_uids"][0]: change["review_evidence"]["text"]
        for change in checkpoint["args"]["trace"]["changes"]
    }
    assert evidence_by_source == comments
    assert len(calls) == 2


def test_partial_atomize_review_isolated_to_answered_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("atomize/partial-comments")
    first = ops.add(ctx, "Use that door for staff.")
    second = ops.add(ctx, "Use that entrance after hours.")
    store.save(ctx)
    store.set_current(ctx.name)
    calls: list[dict] = []

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
            calls.append(payload)
            return json.dumps(
                _aggregate_response(payload, {
                    "items": [
                        {
                            "candidate_id": memory["candidate_id"],
                            "classification": (
                                "ATOMIC"
                                if memory["declared_frame"] is not None
                                else "UNCERTAIN"
                            ),
                            "reason_codes": [
                                (
                                    "A01_ONE_FOCUS"
                                    if memory["declared_frame"] is not None
                                    else "A06_NO_HIDDEN_CONTEXT"
                                )
                            ],
                            "children": [],
                            "reason": (
                                "The local frame resolves this referent."
                                if memory["declared_frame"] is not None
                                else "This referent remains unresolved."
                            ),
                        }
                        for memory in payload["memories"]
                    ]
                })
            )

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        Provider,
    )
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    source_analysis = store.load_atomize_analysis(ctx.uid)
    assert source_analysis is not None
    assert runner.invoke(
        app,
        ["review", "atomize", "--snapshot"],
    ).exit_code == 0
    comment = "'that door' means the staff entrance."
    assert runner.invoke(
        app,
        [
            "review",
            "--respond-to",
            first.uid[:8],
            "--response",
            comment,
        ],
    ).exit_code == 0

    reanalyzed = runner.invoke(app, ["impact", "atomize", "--with-review"])

    assert reanalyzed.exit_code == 0, reanalyzed.output
    assert [
        memory["candidate_id"]
        for memory in calls[-1]["memories"]
    ] == ["m000001", "m000002"]
    assert calls[-1]["memories"][0]["declared_frame"] == comment
    assert calls[-1]["memories"][1]["declared_frame"] is None
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    assert [item.classification for item in analysis.items] == [
        "ATOMIC",
        "UNCERTAIN",
    ]
    assert [frame.memory_uid for frame in analysis.declared_frames] == [
        first.uid
    ]
    assert analysis.declared_frames[0].source_analysis_uid == (
        source_analysis.uid
    )
    assert second.uid not in {
        frame.memory_uid for frame in analysis.declared_frames
    }
