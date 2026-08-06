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
import memcommit.commands.atomize_sessions as atomize_sessions_module
from memcommit.atomize import (
    ATOMIZE_LEGACY_RULESET_VERSION,
    AtomizeAnalysisSession,
    AtomizeImpactError,
    AtomizeQualityIssue,
    AtomizeReading,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.atomize_workbench import (
    atomize_workbench_declared_frames,
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
    _finding_map,
    _list_fragments,
    _list_text,
    _source_map,
    render_atomize_workbench_snapshot,
    run_atomize_workbench_shell,
)
from memcommit.commands.atomize_sessions import (
    atomize_session_entries,
    choose_atomize_session,
    revalidate_saved_atomize_analysis,
)
from memcommit.commands.review_shell import RESPONSE_LABEL
from memcommit.commands.session_picker import SessionNewReceipt, SessionOpenReceipt
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
                        {
                            "label": "Use the prior NFC mechanism",
                            "text": (
                                "It uses the previously described NFC "
                                "mechanism."
                            ),
                        },
                        {
                            "label": "Use the prior NFC credential",
                            "text": (
                                "It accepts the previously described "
                                "credential."
                            ),
                        },
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
                                {
                                    "label": "Same NFC mechanism",
                                    "text": "The same NFC mechanism.",
                                },
                                {
                                    "label": "Same NFC credential",
                                    "text": "The same NFC credential.",
                                },
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
                                {
                                    "label": "This entrance",
                                    "text": (
                                        "The NFC rule concerns this entrance."
                                    ),
                                },
                                {
                                    "label": "Another entrance",
                                    "text": (
                                        "The NFC rule concerns another "
                                        "entrance."
                                    ),
                                },
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


def test_context_clean_quality_scan_does_not_duplicate_source_uncertainty():
    ctx = ops.init("aggregate/context-clean")
    ops.add(ctx, "The main entrance closes at 5 p.m.")
    ops.add(ctx, "After that time, a student card is required.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    # A compliant quality scan may resolve the antecedent from the complete
    # Context even though source-only atomization remains conservative.
    report = replace(
        report,
        items=(
            replace(
                report.items[0],
                classification="ATOMIC",
                reason_codes=("A01_ONE_FOCUS",),
                reason="The entrance-hours source has one focus.",
            ),
            replace(
                report.items[1],
                classification="UNCERTAIN",
                reason_codes=("A06_NO_HIDDEN_CONTEXT",),
                reason=(
                    "The target's time antecedent is unavailable source-locally."
                ),
            ),
        ),
        quality_issues=(),
    )
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)

    assert workbench.issue_count == 1
    assert workbench.issues[0].uid.startswith("atomize:")


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
        assert "WHAT HAPPENED" in output
        assert "WHAT REMAINS UNRESOLVED" in output
        assert "REPRESENTATIVE / BOUNDARY CASES" in output
    assert "ISSUES" in first.output
    assert "REVIEW ITEMS" in review.output
    assert RESPONSE_LABEL in first.output
    assert "EXACT RESULTS" in review.output
    assert RESPONSE_LABEL not in review.output
    resumed = store.load_atomize_workbench(analysis)
    assert resumed is not None
    assert resumed.uid == workbench.uid
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert store.list_checkpoints(ctx.name) == checkpoints_before


def test_atomize_sessions_catalog_reopens_exact_analysis_provider_free(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    provider = AggregateProvider()
    _patch_provider(monkeypatch, provider)
    created = runner.invoke(app, ["impact", "atomize"])
    assert created.exit_code == 0, created.output
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None

    entries = atomize_session_entries(store)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.key == analysis.uid
    assert entry.title == ctx.name
    assert entry.group == ctx.name
    assert entry.status == "CURRENT"
    assert entry.reopen_argv == (
        "mem",
        "atomize",
        "--context",
        ctx.name,
    )
    assert "not executed by the picker" in entry.detail

    other = ops.init("unrelated/current")
    ops.add(other, "Unrelated Memory.")
    store.save(other)
    store.set_current(other.name)
    before = store._context_file(ctx.name).read_bytes()
    monkeypatch.setattr(
        "memcommit.commands.atomize.choose_atomize_session",
        lambda _store, *, show_all: SessionOpenReceipt(
            kind="atomize",
            key=entry.key,
            argv=entry.reopen_argv,
        ),
    )

    def provider_must_not_connect():
        raise AssertionError("saved selection must be provider-free")

    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        provider_must_not_connect,
    )
    resumed = runner.invoke(app, ["atomize", "--sessions"])

    assert resumed.exit_code == 0, resumed.output
    assert "Resumed; the provider was not called." in resumed.output
    assert store.current_context_name() == other.name
    assert store._context_file(ctx.name).read_bytes() == before
    assert len(provider.payloads) == 1


def test_atomize_sessions_empty_and_forged_receipts_fail_closed(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    monkeypatch.setattr(
        "memcommit.commands.atomize_sessions.choose_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("empty catalog must not open the picker")
        ),
    )

    assert choose_atomize_session(store) is None
    empty = runner.invoke(app, ["atomize", "--sessions"])
    assert empty.exit_code == 0, empty.output
    assert "Atomize selection ended; no analysis was opened." in empty.output

    class TTY:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(atomize_sessions_module.sys, "stdin", TTY())
    monkeypatch.setattr(atomize_sessions_module.sys, "stdout", TTY())
    new_receipt = SessionNewReceipt(kind="atomize", argv=("mem", "atomize"))
    monkeypatch.setattr(
        "memcommit.commands.atomize_sessions.choose_session",
        lambda entries, **kwargs: (
            new_receipt
            if entries == () and kwargs["new_receipt"] == new_receipt
            else pytest.fail("empty Atomize must offer New")
        ),
    )
    assert choose_atomize_session(store) == new_receipt

    ctx, _ = _init_context(store)
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize_sessions.choose_session",
        lambda *_args, **_kwargs: SessionOpenReceipt(
            kind="atomize",
            key=opened.analysis.uid,
            argv=("mem", "atomize", "--save"),
        ),
    )

    with pytest.raises(ValueError, match="forged receipt"):
        choose_atomize_session(store)


def test_atomize_session_selection_rechecks_persisted_identity(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )
    entry = atomize_session_entries(store)[0]

    def remove_selected(_store, *, show_all):
        store.delete_atomize_workbench(ctx.uid)
        store.delete_atomize_analysis(ctx.uid)
        return SessionOpenReceipt(
            kind="atomize",
            key=opened.analysis.uid,
            argv=entry.reopen_argv,
        )

    monkeypatch.setattr(
        "memcommit.commands.atomize.choose_atomize_session",
        remove_selected,
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("missing selection must not refresh")
        ),
    )

    result = runner.invoke(app, ["atomize", "--sessions"])

    assert result.exit_code == 1
    assert "is no longer available" in result.output
    assert store.load_atomize_analysis(ctx.uid) is None


def test_atomize_sessions_refuse_legacy_ruleset_without_provider_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )
    legacy = replace(
        opened.analysis,
        ruleset_version=ATOMIZE_LEGACY_RULESET_VERSION,
    )
    store.save_atomize_analysis(legacy)
    entry = atomize_session_entries(store)[0]
    assert entry.status == "STALE"
    monkeypatch.setattr(
        "memcommit.commands.atomize.choose_atomize_session",
        lambda _store, *, show_all: SessionOpenReceipt(
            kind="atomize",
            key=legacy.uid,
            argv=entry.reopen_argv,
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(
            AssertionError("legacy selection must not refresh")
        ),
    )

    result = runner.invoke(app, ["atomize", "--sessions"])

    assert result.exit_code == 1
    assert "older semantic ruleset" in result.output
    saved = store.load_atomize_analysis(ctx.uid)
    assert saved is not None
    assert saved.uid == legacy.uid
    assert saved.ruleset_version == ATOMIZE_LEGACY_RULESET_VERSION


def test_atomize_sessions_mark_a_legacy_ruleset_stale(isolated_store):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )
    legacy_data = opened.analysis.to_dict()
    legacy_data["schema_version"] = 1
    legacy_data["ruleset_version"] = "atomize-v1-draft"
    for field in (
        "declared_frames",
        "source_review_uid",
        "source_review_digest",
        "overview",
        "quality_issues",
    ):
        legacy_data.pop(field)
    for item in legacy_data["items"]:
        for child in item["children"]:
            child.pop("frame_spans")
    legacy = AtomizeAnalysisSession.from_dict(legacy_data)
    store.delete_atomize_workbench(ctx.uid)
    store.save_atomize_analysis(legacy)

    assert atomize_session_entries(store)[0].status == "STALE"
    with pytest.raises(ValueError, match="older semantic ruleset"):
        revalidate_saved_atomize_analysis(store, legacy)


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
                label="This entrance",
                text="The NFC rule concerns this entrance.",
            ),
            AtomizeReading(
                uid=f"conflict:{first.uid}:{second.uid}:reading:2",
                role="COMPETING",
                label="Another entrance",
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
    issue_list = snapshot.split("\n\nAMBIGUITY 1/", 1)[0]
    assert (
        "WHY · “same NFC” can denote a mechanism or credential"
        in issue_list
    )
    assert "↳ R1 · Use the prior NFC mechanism" in issue_list
    assert "↳ R2 · Use the prior NFC credential" in issue_list
    assert "It uses the previously described NFC mechanism." not in issue_list
    assert "It uses the previously described NFC mechanism." in snapshot
    assert issue_list.count("↳ R") == 2
    assert "READING OPTIONS" not in issue_list

    saved: list[dict] = []
    with create_pipe_input() as pipe_input:
        # Open issue 1 from Items, focus its combined Decision, choose reading
        # 2, leave option navigation, then use the Response compatibility key
        # to open and save the same inline field.
        pipe_input.send_text(
            "\x1b[B\r\x1b[B\x1b[B\r\x1b[B\r"
            "\x7fcNeeds the staff-only qualifier.\x13q"
        )
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
    frames, _ = atomize_workbench_declared_frames(workbench, analysis)
    assert (
        "Selected ordinary reading: "
        "It accepts the previously described credential."
    ) in frames[next(iter(frames))]
    assert "Selected ordinary reading: Use the prior NFC credential" not in (
        frames[next(iter(frames))]
    )
    assert saved


def test_enter_drills_into_readings_and_toggles_the_selected_choice():
    ctx = ops.init("workbench/reading-drilldown")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    first = workbench.ordered_issues()[0]

    expanded = _list_text(
        workbench,
        analysis,
        _finding_map(analysis),
        _source_map(analysis),
        expanded_issue_uid=first.uid,
        reading_index=1,
    )
    assert "It accepts the previously described credential." in expanded
    assert "› ○ 2. [ALTERNATIVE]" in expanded
    fragments = _list_fragments(
        workbench,
        analysis,
        _finding_map(analysis),
        _source_map(analysis),
        expanded_issue_uid=first.uid,
        reading_index=1,
    )
    cursor_markers = [
        index
        for index, fragment in enumerate(fragments)
        if fragment[0] == "[SetCursorPosition]"
    ]
    assert len(cursor_markers) == 1
    cursor_line = fragments[cursor_markers[0] + 1][1]
    assert cursor_line.lstrip().startswith("› ○ 2. [ALTERNATIVE]")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[B\r\x1b[B\x1b[B\r\x1b[B\rq"
        )
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert workbench.response_for(
        first.uid
    ).selected_choice_uid.endswith(":reading:2")

    # Reopening starts on the selected reading. Entering it again clears the
    # selection, so a separate numeric "clear" command is unnecessary.
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r\x1b[B\x1b[B\r\rq")
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert workbench.response_for(first.uid).selected_choice_uid is None


def test_atomize_shell_embeds_read_only_result_case_navigation() -> None:
    ctx = ops.init("workbench/result-view")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    before = workbench.to_dict()
    saved: list[dict] = []

    with create_pipe_input() as pipe_input:
        # V opens the shared result view, Enter expands its selected case,
        # Backspace collapses it, and V returns to the complete issue ledger.
        pipe_input.send_text("v\r\x7fvq")
        result = run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: saved.append(session.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is workbench
    assert workbench.answered_count == 0
    assert workbench.cursor_uid == before["cursor_uid"]
    assert all(
        not response.answered for response in workbench.responses.values()
    )
    assert saved
    assert saved[-1]["analysis_uid"] == before["analysis_uid"]


def test_drilldown_back_and_numeric_keys_do_not_change_a_reading():
    ctx = ops.init("workbench/reading-back")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    first = workbench.ordered_issues()[0]
    saved: list[dict] = []

    with create_pipe_input() as pipe_input:
        # Opening, hovering reading 2, and going back are presentation-only.
        # The former direct numeric shortcut is intentionally inert.
        pipe_input.send_text("\r\x1b[B\x7f2q")
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: saved.append(session.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert workbench.cursor_uid == first.uid
    assert workbench.response_for(first.uid).selected_choice_uid is None
    assert len(saved) == 1


def test_response_backspace_still_edits_text_instead_of_navigating_up():
    ctx = ops.init("workbench/response-backspace")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    first = workbench.ordered_issues()[0]

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[B\r\x1b[B\x1b[B\x1b[B\rab\x7f\rq"
        )
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert workbench.response_for(first.uid).text == "a"


def test_enter_expands_and_closes_an_issue_without_readings():
    ctx = ops.init("workbench/detail-only-drilldown")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    workbench.move(1)
    issue = workbench.current_issue()
    assert issue is not None
    assert not issue.choice_uids

    expanded = _list_text(
        workbench,
        analysis,
        _finding_map(analysis),
        _source_map(analysis),
        expanded_issue_uid=issue.uid,
    )
    assert "ATOMIZE UNCERTAINTY 2/2" in expanded
    assert "Which local reading or scope should govern this source?" in (
        expanded
    )

    saved: list[dict] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r\rq")
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: saved.append(session.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert workbench.cursor_uid == issue.uid
    assert len(saved) == 1


def test_tui_up_and_down_follow_the_vertical_issue_list():
    ctx = ops.init("workbench/vertical-navigation")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    ordered = workbench.ordered_issues()
    assert len(ordered) == 2

    saved: list[dict] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\x1b[B\rq")
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: saved.append(session.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert workbench.cursor_uid == ordered[1].uid
    assert workbench.response_for(ordered[0].uid).selected_choice_uid is None

    with create_pipe_input() as pipe_input:
        # Start from the report row, move down to issue 2, then back up to
        # issue 1. Moving the Items cursor is only a preview; Enter explicitly
        # opens that row and updates the durable workbench cursor.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[A\rq")
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: saved.append(session.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert workbench.cursor_uid == ordered[0].uid
    assert saved


def test_shared_atomize_shell_preserves_durable_sort_toggle():
    ctx = ops.init("workbench/shared-sort")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    assert workbench.sort_mode == "SOURCE"

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("sq")
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert workbench.sort_mode == "PRIORITY"


def test_issue_list_uses_labels_and_discloses_additional_readings():
    ctx = ops.init("workbench/reading-preview")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    issue = report.quality_issues[0]
    full_alternative = (
        "This complete alternative remains available and selectable in "
        "the detail panel."
    )
    hidden_alternative = "A third full reading remains available in detail."
    readings = (
        issue.readings[0],
        replace(
            issue.readings[1],
            label="Short alternative label",
            text=full_alternative,
        ),
        AtomizeReading(
            uid=f"{issue.uid}:reading:3",
            role="ALTERNATIVE",
            label="A third reading",
            text=hidden_alternative,
        ),
    )
    analysis = create_atomize_analysis(
        ctx,
        replace(
            report,
            quality_issues=(
                replace(issue, readings=readings),
            ),
        ),
    )
    snapshot = render_atomize_workbench_snapshot(
        create_atomize_workbench(analysis),
        analysis,
    )
    issue_list = snapshot.split("\n\nAMBIGUITY 1/", 1)[0]

    assert "↳ R1 · Use the prior NFC mechanism" in issue_list
    assert "↳ R2 · Short alternative label" in issue_list
    assert full_alternative not in issue_list
    assert full_alternative in snapshot
    assert "↳ +1 more reading (open detail)" in issue_list
    assert hidden_alternative not in issue_list
    assert hidden_alternative in snapshot


def test_schema_v3_readings_resume_with_full_text_as_legacy_label():
    ctx = ops.init("workbench/legacy-reading-label")
    ops.add(ctx, "Use the same NFC.")
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    legacy = analysis.to_dict()
    legacy["schema_version"] = 3
    for issue in legacy["quality_issues"]:
        for reading in issue["readings"]:
            reading.pop("label")

    restored = AtomizeAnalysisSession.from_dict(legacy)
    snapshot = render_atomize_workbench_snapshot(workbench, restored)

    restored_reading = restored.quality_issues[0].readings[0]
    assert restored_reading.label == restored_reading.text
    assert restored.to_dict()["schema_version"] == 4
    assert (
        "↳ R1 · It uses the previously described NFC mechanism."
        in snapshot
    )
