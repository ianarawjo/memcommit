"""End-to-end contracts for the saved atomize overview and issue workbench."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.atomize import (
    AtomizeImpactError,
    AtomizeQualityIssue,
    AtomizeReading,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.atomize_workbench import (
    atomize_workbench_response_digest,
    create_atomize_workbench,
)
from memcommit.atomize_workflow import (
    ATOMIZE_AGGREGATE_TIMEOUT_SECONDS,
    _connect_aggregate_atomize_provider,
    open_or_create_atomize_workbench,
)
from memcommit.cli import app
from memcommit.commands.atomize_workbench_shell import (
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.commands.review_shell import RESPONSE_LABEL
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore


runner = CliRunner()
PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


class AggregateProvider:
    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        assert set(output_schema["required"]) == {
            "overview",
            "items",
            "quality_issues",
        }
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        memories = payload["memories"]
        first = memories[0]
        reviewed = first["declared_frame"] is not None
        items = []
        for index, memory in enumerate(memories):
            if index == 0 and not reviewed:
                classification = "UNCERTAIN"
                reason_codes = ["A06_NO_HIDDEN_CONTEXT"]
                reason = (
                    "“same NFC” has no local antecedent, so the accepted "
                    "credential and a safe stand-alone claim cannot be "
                    "determined."
                )
            else:
                classification = "ATOMIC"
                reason_codes = ["A01_ONE_FOCUS"]
                reason = "The source has one independently revisable focus."
            items.append(
                {
                    "candidate_id": memory["candidate_id"],
                    "classification": classification,
                    "reason_codes": reason_codes,
                    "children": [],
                    "reason": reason,
                }
            )
        overview = {
            "understood": {
                "text": (
                    "The notes describe an NFC-based access rule and retain "
                    "the original operational wording."
                ),
                "source_ids": [first["candidate_id"]],
            },
            "changed": {
                "text": (
                    "No source is split in this preview; each original Memory "
                    "remains addressable."
                ),
                "source_ids": [first["candidate_id"]],
            },
            "unresolved": {
                "text": (
                    ""
                    if reviewed
                    else "The antecedent of “same NFC” remains unresolved."
                ),
                "source_ids": (
                    [] if reviewed else [first["candidate_id"]]
                ),
            },
        }
        quality_issues = (
            []
            if reviewed
            else [
                {
                    "kind": "AMBIGUITY",
                    "source_ids": [first["candidate_id"]],
                    "interpretation": "DOMINANT",
                    "clarification": "REQUIRED",
                    "conflict": "NONE",
                    "ordinary_readings": [
                        "It uses the previously described NFC mechanism.",
                        "It accepts the previously described credential.",
                    ],
                    "scope_dimensions": [],
                    "reason": (
                        "“same NFC” can denote a mechanism or credential, "
                        "so the accepted access method cannot be determined."
                    ),
                    "question": (
                        "Does “same NFC” mean the mechanism or credential?"
                    ),
                }
            ]
        )
        return json.dumps(
            {
                "overview": overview,
                "items": items,
                "quality_issues": quality_issues,
            }
        )


def _init_context(store: MemoryStore):
    ctx = ops.init("temp/task-1")
    memory = ops.add(ctx, "Use the same NFC for access.")
    store.save(ctx)
    store.set_current(ctx.name)
    return ctx, memory


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )


def test_aggregate_atomize_extends_only_the_concrete_codex_timeout():
    provider = CodexChatGPTProvider(
        binary=Path("/unused/codex"),
        env={},
        timeout=120,
    )

    connected = _connect_aggregate_atomize_provider(lambda: provider)

    assert connected is provider
    assert provider.timeout == ATOMIZE_AGGREGATE_TIMEOUT_SECONDS
    fake = AggregateProvider()
    assert _connect_aggregate_atomize_provider(lambda: fake) is fake


def test_aggregate_analysis_preserves_overview_and_typed_issue_arity():
    ctx = ops.init("aggregate")
    first = ops.add(ctx, "Use the same NFC.")
    second = ops.add(ctx, "The entrance closes at 5 p.m.")

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
            first_id, second_id = [
                memory["candidate_id"] for memory in payload["memories"]
            ]
            return json.dumps(
                {
                    "overview": {
                        "understood": {
                            "text": "The notes describe access credentials.",
                            "source_ids": [first_id],
                        },
                        "changed": {
                            "text": "Both sources remain intact.",
                            "source_ids": [first_id, second_id],
                        },
                        "unresolved": {
                            "text": "The NFC antecedent is unresolved.",
                            "source_ids": [first_id],
                        },
                    },
                    "items": [
                        {
                            "candidate_id": first_id,
                            "classification": "UNCERTAIN",
                            "reason_codes": ["A06_NO_HIDDEN_CONTEXT"],
                            "children": [],
                            "reason": "The NFC antecedent is unavailable.",
                        },
                        {
                            "candidate_id": second_id,
                            "classification": "ATOMIC",
                            "reason_codes": ["A01_ONE_FOCUS"],
                            "children": [],
                            "reason": "The source has one focus.",
                        },
                    ],
                    "quality_issues": [
                        {
                            "kind": "AMBIGUITY",
                            "source_ids": [first_id],
                            "interpretation": "DOMINANT",
                            "clarification": "REQUIRED",
                            "conflict": "NONE",
                            "ordinary_readings": [
                                "The same NFC mechanism.",
                                "The same NFC credential.",
                            ],
                            "scope_dimensions": [],
                            "reason": (
                                "The referent is unclear, so the accepted "
                                "credential cannot be determined."
                            ),
                            "question": "Which NFC relation is intended?",
                        },
                        {
                            "kind": "CONFLICT",
                            "source_ids": [first_id, second_id],
                            "interpretation": "NONE",
                            "clarification": "REQUIRED",
                            "conflict": "MAY",
                            "ordinary_readings": [
                                "The NFC rule concerns this entrance.",
                                "The NFC rule concerns another entrance.",
                            ],
                            "scope_dimensions": ["PLACE"],
                            "reason": (
                                "The place scope changes whether the access "
                                "rule conflicts with the closing time."
                            ),
                            "question": "Which entrance does the NFC rule use?",
                        },
                    ],
                }
            )

    report = impact_atomize(ctx, Provider)

    assert report.overview is not None
    assert report.overview.understood.source_uids == (first.uid,)
    assert [issue.kind for issue in report.quality_issues] == [
        "AMBIGUITY",
        "CONFLICT",
    ]
    assert report.quality_issues[0].source_uids == (first.uid,)
    assert report.quality_issues[1].source_uids == (
        first.uid,
        second.uid,
    )
    assert [reading.role for reading in report.quality_issues[0].readings] == [
        "DOMINANT",
        "ALTERNATIVE",
    ]
    analysis = create_atomize_analysis(ctx, report)
    snapshot = render_atomize_workbench_snapshot(
        create_atomize_workbench(analysis),
        analysis,
    )
    assert "CONFLICT · MAY" in snapshot
    assert "CONFLICT · CONFLICT" not in snapshot


def test_aggregate_contract_rejects_items_without_overview_or_quality_scan():
    ctx = ops.init("aggregate/strict")
    ops.add(ctx, "One direct Memory.")

    class ItemsOnlyProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
            return json.dumps(
                {
                    "items": [
                        {
                            "candidate_id": payload["memories"][0][
                                "candidate_id"
                            ],
                            "classification": "ATOMIC",
                            "reason_codes": ["A01_ONE_FOCUS"],
                            "children": [],
                            "reason": "The source has one focus.",
                        }
                    ]
                }
            )

    with pytest.raises(AtomizeImpactError, match="structured output"):
        impact_atomize(ctx, ItemsOnlyProvider)


def test_cli_reuses_one_analysis_across_impact_atomize_and_review(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    provider = AggregateProvider()
    _patch_provider(monkeypatch, provider)
    context_before = store._context_file(ctx.name).read_bytes()
    checkpoints_before = store.list_checkpoints(ctx.name)

    first = runner.invoke(app, ["impact", "atomize"])
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None

    second = runner.invoke(app, ["impact", "atomize"])
    direct = runner.invoke(app, ["atomize"])
    review = runner.invoke(app, ["review", "atomize", "--snapshot"])

    assert first.exit_code == second.exit_code == direct.exit_code == 0
    assert review.exit_code == 0
    assert len(provider.payloads) == 1
    assert f"Analysis [{analysis.uid[:8]}]" in first.output
    assert "the provider was not called" in second.output
    assert "the provider was not called" in direct.output
    for output in [first.output, review.output]:
        assert "WHAT MEM UNDERSTOOD" in output
        assert "WHAT CHANGED / REMAINS UNRESOLVED" in output
        assert "ISSUES" in output
        assert RESPONSE_LABEL in output
    resumed = store.load_atomize_workbench(analysis)
    assert resumed is not None
    assert resumed.uid == workbench.uid
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert store.list_checkpoints(ctx.name) == checkpoints_before


def test_refresh_rolls_back_analysis_if_workbench_save_fails(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    first_provider = AggregateProvider()
    first = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=lambda: first_provider,
    )
    original_analysis = store._atomize_analysis_path(ctx.uid).read_bytes()
    original_workbench = store._atomize_workbench_path(ctx.uid).read_bytes()
    original_save = MemoryStore.save_atomize_workbench

    def fail_for_replacement(self, session):
        if session.analysis_uid != first.analysis.uid:
            raise OSError("injected workbench save failure")
        return original_save(self, session)

    monkeypatch.setattr(
        MemoryStore,
        "save_atomize_workbench",
        fail_for_replacement,
    )
    replacement_provider = AggregateProvider()

    with pytest.raises(OSError, match="injected workbench"):
        open_or_create_atomize_workbench(
            store=store,
            ctx=ctx,
            provider_factory=lambda: replacement_provider,
            refresh=True,
        )

    restored = store.load_atomize_analysis(ctx.uid)
    assert restored is not None and restored.uid == first.analysis.uid
    assert store._atomize_analysis_path(ctx.uid).read_bytes() == original_analysis
    assert store._atomize_workbench_path(ctx.uid).read_bytes() == original_workbench


def test_refresh_is_explicit_and_stale_analysis_fails_closed(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, memory = _init_context(store)
    provider = AggregateProvider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    first = store.load_atomize_analysis(ctx.uid)
    assert first is not None

    refreshed = runner.invoke(
        app,
        ["impact", "atomize", "--refresh"],
    )
    second = store.load_atomize_analysis(ctx.uid)
    assert refreshed.exit_code == 0
    assert second is not None and second.uid != first.uid
    assert len(provider.payloads) == 2

    changed = store.load_direct(ctx.name)
    changed.replace(
        type(memory)(uid=memory.uid, content="Changed access rule.")
    )
    store.save(changed)
    stale = runner.invoke(app, ["impact", "atomize"])

    assert stale.exit_code == 1
    assert "stale" in stale.output
    assert len(provider.payloads) == 2
    assert store.load_atomize_analysis(ctx.uid).uid == second.uid


def test_workbench_response_reanalysis_and_save_gate_keep_provenance(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, memory = _init_context(store)
    provider = AggregateProvider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(app, ["impact", "atomize"]).exit_code == 0
    source_analysis = store.load_atomize_analysis(ctx.uid)
    assert source_analysis is not None
    source_workbench = store.load_atomize_workbench(source_analysis)
    assert source_workbench is not None
    checkpoints_before = store.list_checkpoints(ctx.name)

    comment = "'same NFC' means the staff-door NFC credential."
    responded = runner.invoke(
        app,
        [
            "review",
            "atomize",
            "--respond-to",
            f"atomize:{memory.uid[:8]}",
            "--response",
            comment,
        ],
    )
    blocked = runner.invoke(app, ["atomize", "--save"])

    assert responded.exit_code == 0
    assert blocked.exit_code == 1
    assert "have not been incorporated" in blocked.output
    assert len(provider.payloads) == 1
    assert store.list_checkpoints(ctx.name) == checkpoints_before

    reanalyzed = runner.invoke(
        app,
        ["impact", "atomize", "--with-review"],
    )
    current = store.load_atomize_analysis(ctx.uid)

    assert reanalyzed.exit_code == 0, reanalyzed.output
    assert current is not None and current.uid != source_analysis.uid
    assert provider.payloads[-1]["memories"][0]["declared_frame"] == comment
    assert current.source_review_uid == source_workbench.uid
    assert current.declared_frames[0].review_item_uid.startswith("atomize:")
    assert store.list_checkpoints(ctx.name) == checkpoints_before


def test_reviewed_reanalysis_preserves_mixed_pairwise_responses_by_failing_closed(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, first = _init_context(store)
    second = ops.add(ctx, "The entrance closes at 5 p.m.")
    store.save(ctx)
    report = impact_atomize(ctx, lambda: AggregateProvider())
    conflict = AtomizeQualityIssue(
        uid=f"conflict:{first.uid}:{second.uid}",
        kind="CONFLICT",
        source_uids=(first.uid, second.uid),
        conflict="MAY",
        readings=(
            AtomizeReading(
                uid=f"conflict:{first.uid}:{second.uid}:reading:1",
                role="COMPETING",
                text="The NFC rule concerns this entrance.",
            ),
            AtomizeReading(
                uid=f"conflict:{first.uid}:{second.uid}:reading:2",
                role="COMPETING",
                text="The NFC rule concerns another entrance.",
            ),
        ),
        scope_dimensions=("PLACE",),
        reason=(
            "The place scope changes whether the access rule conflicts with "
            "the closing time."
        ),
        question="Which entrance does the NFC rule use?",
    )
    analysis = create_atomize_analysis(
        ctx,
        replace(
            report,
            quality_issues=report.quality_issues + (conflict,),
        ),
    )
    workbench = create_atomize_workbench(analysis)
    workbench.response_for(f"ambiguity:{first.uid}").text = (
        "Use the staff-door NFC credential."
    )
    workbench.response_for(conflict.uid).text = (
        "The closing time applies to that same staff door."
    )
    store.save_atomize_analysis(analysis)
    store.save_atomize_workbench(workbench)
    original_digest = atomize_workbench_response_digest(workbench)

    class NeverCalled:
        calls = 0

        def complete(self, prompt, *, operation, output_schema=None):
            self.calls += 1
            raise AssertionError("provider must not be called")

    provider = NeverCalled()
    _patch_provider(monkeypatch, provider)
    result = runner.invoke(
        app,
        ["impact", "atomize", "--with-review"],
    )

    assert result.exit_code == 1
    assert "Pairwise conflict responses" in result.output
    assert provider.calls == 0
    current_analysis = store.load_atomize_analysis(ctx.uid)
    assert current_analysis is not None
    assert current_analysis.uid == analysis.uid
    current_workbench = store.load_atomize_workbench(current_analysis)
    assert current_workbench is not None
    assert atomize_workbench_response_digest(
        current_workbench
    ) == original_digest


def test_reviewed_reanalysis_rejects_two_unary_origins_for_one_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, memory = _init_context(store)
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    workbench.response_for(f"ambiguity:{memory.uid}").text = (
        "The antecedent is the staff-door credential."
    )
    workbench.response_for(f"atomize:{memory.uid}").text = (
        "Retain the staff-only scope."
    )
    store.save_atomize_analysis(analysis)
    store.save_atomize_workbench(workbench)
    original_digest = atomize_workbench_response_digest(workbench)

    class NeverCalled:
        calls = 0

        def complete(self, prompt, *, operation, output_schema=None):
            self.calls += 1
            raise AssertionError("provider must not be called")

    provider = NeverCalled()
    _patch_provider(monkeypatch, provider)
    result = runner.invoke(
        app,
        ["impact", "atomize", "--with-review"],
    )

    assert result.exit_code == 1
    assert "More than one answered unary issue" in result.output
    assert provider.calls == 0
    current_analysis = store.load_atomize_analysis(ctx.uid)
    assert current_analysis is not None
    assert current_analysis.uid == analysis.uid
    current_workbench = store.load_atomize_workbench(current_analysis)
    assert current_workbench is not None
    assert atomize_workbench_response_digest(
        current_workbench
    ) == original_digest


def test_snapshot_and_tui_keep_typed_detail_and_combined_response():
    ctx = ops.init("workbench/ui")
    ops.add(ctx, "Use the same NFC.")
    provider = AggregateProvider()
    report = impact_atomize(ctx, lambda: provider)
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)

    snapshot = render_atomize_workbench_snapshot(workbench, analysis)
    assert "AMBIGUITY" in snapshot
    assert "ATOMIZE UNCERTAINTY" in snapshot
    assert "[DOMINANT]" in snapshot
    assert "[ALTERNATIVE]" in snapshot
    assert snapshot.count(RESPONSE_LABEL) == 1
    assert "WHY THIS IS UNCLEAR" in snapshot

    saved: list[dict] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("2\rNeeds the staff-only qualifier.\x13q")
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: saved.append(session.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    first_issue = workbench.ordered_issues()[0]
    response = workbench.response_for(first_issue.uid)
    assert response.selected_choice_uid.endswith(":reading:2")
    assert response.text == "Needs the staff-only qualifier."
    assert saved
