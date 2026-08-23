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
import memcommit.commands.atomize as atomize_command
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
from memcommit.atomize_resolution_adapter import AtomizeResolutionWorkbenchAdapter
from memcommit.atomize_workbench import (
    atomize_workbench_declared_frames,
    atomize_workbench_response_digest,
    create_atomize_workbench,
    project_atomize_workbench_findings,
)
from memcommit.atomize_workflow import (
    ATOMIZE_AGGREGATE_TIMEOUT_SECONDS,
    _connect_aggregate_atomize_provider,
    open_or_create_atomize_workbench,
)
from memcommit.cli import app
from memcommit.commands.atomize import _materialize_reviewed_workbench
from memcommit.interfaces.tui.operations.atomize.screen import (
    _finding_map,
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
from memcommit.commands.endpoint_setup_flows import AtomizeSetupReceipt
from memcommit.interfaces.tui.workbenches.review import RESPONSE_LABEL
from memcommit.interfaces.tui.workbenches.resolution import ResolutionDestination
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerLocation,
)
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.resolution_workbench import ResolutionWorkbenchAction
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
                "source_ids": ([] if reviewed else [first["candidate_id"]]),
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
                            "text": ("It uses the previously described NFC mechanism."),
                        },
                        {
                            "label": "Use the prior NFC credential",
                            "text": ("It accepts the previously described credential."),
                        },
                    ],
                    "scope_dimensions": [],
                    "reason": (
                        "“same NFC” can denote a mechanism or credential, "
                        "so the accepted access method cannot be determined."
                    ),
                    "question": ("Does “same NFC” mean the mechanism or credential?"),
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


class SplitProvider:
    """Return deterministic two-child splits for compact receipt tests."""

    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        memories = payload["memories"]
        items = []
        source_ids = []
        for memory in memories:
            source_ids.append(memory["candidate_id"])
            first, second = memory["content"].split(" | ", 1)
            items.append(
                {
                    "candidate_id": memory["candidate_id"],
                    "classification": "COMPOSITE",
                    "reason_codes": ["A01_ONE_FOCUS", "A04_SOURCE_GROUNDED"],
                    "children": [
                        {"content": first, "source_spans": [first]},
                        {"content": second, "source_spans": [second]},
                    ],
                    "reason": "The source contains two independently revisable claims.",
                }
            )
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "Each source records two independent claims.",
                        "source_ids": source_ids,
                    },
                    "changed": {
                        "text": "Each source is split into its two recorded claims.",
                        "source_ids": source_ids,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": items,
                "quality_issues": [],
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


def test_atomize_auto_types_bare_memory_and_finds_its_owner(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("atomize/source")
    selected = ops.add(source, "Use the same NFC for staff access.")
    ops.add(source, "The visitor entrance closes at five.")
    current = ops.init("atomize/current")
    for context in (source, current):
        store.save(context)
    store.set_current(current.name)
    provider = AggregateProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(app, ["atomize", selected.uid[:7]])

    assert result.exit_code == 0, result.output
    analysis = store.load_atomize_analysis(source.uid)
    assert analysis is not None
    assert analysis.context_name == source.name
    assert analysis.memory_count == 1
    assert tuple(item.memory_uid for item in analysis.items) == (selected.uid,)
    assert store.current_context_name() == current.name
    assert len(provider.payloads) == 1


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
                                    "text": ("The NFC rule concerns this entrance."),
                                },
                                {
                                    "label": "Another entrance",
                                    "text": ("The NFC rule concerns another entrance."),
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
                            "candidate_id": payload["memories"][0]["candidate_id"],
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
                reason=("The target's time antecedent is unavailable source-locally."),
            ),
        ),
        quality_issues=(),
    )
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)

    assert workbench.issue_count == 1
    assert workbench.issues[0].uid.startswith("atomize:")


def test_cli_reuses_one_analysis_then_bare_atomize_applies_and_review_reopens(
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
    assert "ATOMIZE APPLIED" in direct.output
    for output in [first.output, review.output]:
        assert "WHAT MEM UNDERSTOOD" in output
        assert "WHAT HAPPENED" in output
        assert "WHAT REMAINS UNRESOLVED" in output
        assert "REPRESENTATIVE / BOUNDARY CASES" in output
    assert "ISSUES" in first.output
    assert "REVIEW ITEMS" in review.output
    assert RESPONSE_LABEL in first.output
    # Atomize keeps exact proposed children beside their source finding. The
    # empty generic Resolution result slot must not read as zero projection.
    assert "EXACT RESULTS" not in review.output
    assert RESPONSE_LABEL not in review.output
    resumed = store.load_atomize_workbench(analysis)
    assert resumed is not None
    assert resumed.uid == workbench.uid
    assert resumed.application is not None
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert len(store.list_checkpoints(ctx.name)) == len(checkpoints_before) + 1


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
    assert "the picker does not run it" in entry.detail

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


def test_bare_interactive_atomize_applies_the_current_context_without_a_session(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    provider = AggregateProvider()
    _patch_provider(monkeypatch, provider)
    monkeypatch.setattr(
        "memcommit.commands.atomize._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.choose_atomize_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("bare Atomize must not open the session launcher")
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.present_atomize_workbench",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("bare Atomize must not open the workbench")
        ),
    )
    checkpoints_before = store.list_checkpoints(ctx.name)

    result = runner.invoke(app, ["atomize"])

    assert result.exit_code == 0, result.output
    assert "ATOMIZE APPLIED" in result.output
    assert "JUDGMENTS · 2 unresolved findings recorded as applied-as-is" in result.output
    assert "REVIEW · mem review atomize" in result.output
    assert len(provider.payloads) == 1
    assert len(store.list_checkpoints(ctx.name)) == len(checkpoints_before) + 1
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    assert workbench.application is not None


def test_bare_atomize_receipt_samples_content_and_applied_review_remains_complete(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("atomize/direct-current")
    source_contents = [
        (
            "The Main Building entrance accepts a physical NFC card. | "
            "Mobile-app authentication is not accepted at that entrance."
        ),
        (
            "The staff entrance uses the same physical NFC card. | "
            "Staff should not rely on mobile-app authentication."
        ),
        (
            "The library opens at 10:00 on weekends. | "
            "The research desk closes at 16:00."
        ),
        (
            "The north elevator serves floors one through four. | "
            "The fifth floor requires the south elevator."
        ),
    ]
    sources = [ops.add(ctx, content) for content in source_contents]
    store.save(ctx)
    store.set_current(ctx.name)
    provider = SplitProvider()
    _patch_provider(monkeypatch, provider)
    monkeypatch.setattr(
        "memcommit.commands.atomize.choose_atomize_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("bare Atomize must not open the session launcher")
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.present_atomize_workbench",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("bare Atomize must not open the workbench")
        ),
    )

    applied = runner.invoke(app, ["atomize"])

    assert applied.exit_code == 0, applied.output
    assert "ATOMIZE APPLIED" in applied.output
    assert "EFFECTS · SPLIT 4 · CHILDREN 8 · KEEP 0" in applied.output
    assert "REVIEW · mem review atomize" in applied.output
    for source in sources[:3]:
        assert source.content in applied.output
    assert sources[3].content not in applied.output
    assert applied.output.count("SPLIT ") >= 3
    assert "… 1 MORE SPLIT · see REVIEW" in applied.output
    assert len(provider.payloads) == 1

    checkpoints_after_apply = store.list_checkpoints(ctx.name)
    repeated = runner.invoke(app, ["atomize"])
    assert repeated.exit_code == 0, repeated.output
    assert "already applied; no new checkpoint" in repeated.output
    assert store.list_checkpoints(ctx.name) == checkpoints_after_apply
    assert len(provider.payloads) == 1

    # Applying changes the direct-Memory digest, but the exact checkpoint and
    # terminal workbench keep the saved analysis reviewable without mutation.
    reviewed = runner.invoke(app, ["review", "--snapshot"])

    assert reviewed.exit_code == 0, reviewed.output
    assert "APPLIED" in reviewed.output
    assert source_contents[3] in reviewed.output
    assert len(provider.payloads) == 1
    output_before = store._context_file(ctx.name).read_bytes()
    rejected_edit = runner.invoke(
        app,
        [
            "review",
            "atomize",
            "--respond-to",
            sources[0].uid[:8],
            "--response",
            "Change the applied reading.",
        ],
    )
    assert rejected_edit.exit_code == 1
    assert "read-only" in rejected_edit.output
    assert store._context_file(ctx.name).read_bytes() == output_before


def test_atomize_launcher_shows_frozen_profile_and_store_location(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )
    location = SessionPickerLocation(
        profile_name="study-profile",
        store_path=str(isolated_store),
    )
    captured = {}
    monkeypatch.setattr(
        atomize_sessions_module,
        "session_picker_location",
        lambda selected_store: (
            location
            if selected_store is store
            else pytest.fail("launcher must orient to its supplied store")
        ),
    )
    monkeypatch.setattr(
        atomize_sessions_module,
        "choose_session",
        lambda entries, **kwargs: captured.update(
            entries=entries,
            kwargs=kwargs,
        ),
    )

    assert choose_atomize_session(store) is None
    assert captured["kwargs"]["location"] == location
    assert captured["kwargs"]["title"] == "MEM ATOMIZE · SESSIONS"


def test_atomize_launcher_new_persists_input_output_on_shared_workbench(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _ = _init_context(store)
    provider = AggregateProvider()
    _patch_provider(monkeypatch, provider)
    monkeypatch.setattr(
        "memcommit.commands.atomize.choose_atomize_session",
        lambda _store, *, show_all: SessionNewReceipt(
            kind="atomize",
            argv=("mem", "atomize"),
        ),
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.choose_atomize_setup",
        lambda _store: AtomizeSetupReceipt(
            input_name=ctx.name,
            output_name="workbench/atomized-output",
            create_output=True,
        ),
    )

    opened = runner.invoke(app, ["atomize", "--sessions"])

    assert opened.exit_code == 0, opened.output
    analysis = store.load_atomize_analysis(ctx.uid)
    assert analysis is not None
    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    assert workbench.output_context_name == "workbench/atomized-output"
    assert not store.context_exists("workbench/atomized-output")
    assert "INPUT" in opened.output
    assert "OUTPUT" in opened.output
    assert len(provider.payloads) == 1

    resumed = runner.invoke(
        app,
        ["atomize", "--context", ctx.name],
    )
    assert resumed.exit_code == 0, resumed.output
    assert f"ATOMIZE APPLIED · {ctx.name}" in resumed.output
    assert "REVIEW · mem review atomize --context" in resumed.output
    assert not store.context_exists("workbench/atomized-output")
    assert len(provider.payloads) == 1


def test_atomize_launcher_passes_exact_setup_memory_to_command(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(
        atomize_command,
        "choose_atomize_session",
        lambda _store, *, show_all: SessionNewReceipt(
            kind="atomize",
            argv=("mem", "atomize"),
        ),
    )
    monkeypatch.setattr(
        atomize_command,
        "choose_atomize_setup",
        lambda _store: AtomizeSetupReceipt(
            input_name="focused/source",
            output_name="focused/output",
            create_output=True,
            input_memory_uid="memory-uid",
        ),
    )
    calls = []
    monkeypatch.setattr(atomize_command, "cmd", lambda **kwargs: calls.append(kwargs))

    result = runner.invoke(app, ["atomize", "--sessions"])

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "context_name": "focused/source",
            "output_name": "focused/output",
            "show_all": False,
            "memory_selector": "memory-uid",
        }
    ]


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
    planned = open_or_create_atomize_workbench(
        store=store,
        ctx=store.load_direct(ctx.name),
        provider_factory=AggregateProvider,
        output_context_name="workbench/refreshed-output",
    )
    assert planned.workbench.output_context_name == "workbench/refreshed-output"
    assert len(provider.payloads) == 1

    refreshed = runner.invoke(
        app,
        ["impact", "atomize", "--refresh"],
    )
    second = store.load_atomize_analysis(ctx.uid)
    assert refreshed.exit_code == 0
    assert second is not None and second.uid != first.uid
    refreshed_workbench = store.load_atomize_workbench(second)
    assert refreshed_workbench is not None
    assert refreshed_workbench.output_context_name == "workbench/refreshed-output"
    assert len(provider.payloads) == 2

    changed = store.load_direct(ctx.name)
    changed.replace(type(memory)(uid=memory.uid, content="Changed access rule."))
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
    finding = next(
        item
        for item in project_atomize_workbench_findings(source_analysis)
        if memory.uid in item.source_uids
    )
    source_workbench.response_for(finding.uid).text = comment
    store.save_atomize_workbench(source_workbench)
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

    assert responded.exit_code == 1
    assert "execution is not complete" in responded.output
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
    assert current.declared_frames[0].review_item_uid.endswith(memory.uid)
    assert store.list_checkpoints(ctx.name) == checkpoints_before


def test_atomize_session_catalog_isolated_to_supplied_profile_store(tmp_path):
    profile_a = MemoryStore(root=tmp_path / "profile-a")
    profile_b = MemoryStore(root=tmp_path / "profile-b")

    context_a = ops.init("private/a")
    ops.add(context_a, "Only profile A owns this Memory.")
    profile_a.save(context_a)
    opened_a = open_or_create_atomize_workbench(
        store=profile_a,
        ctx=context_a,
        provider_factory=AggregateProvider,
    )

    context_b = ops.init("private/b")
    ops.add(context_b, "Only profile B owns this Memory.")
    profile_b.save(context_b)
    opened_b = open_or_create_atomize_workbench(
        store=profile_b,
        ctx=context_b,
        provider_factory=AggregateProvider,
    )

    entries_a = atomize_session_entries(profile_a)
    entries_b = atomize_session_entries(profile_b)

    assert [(entry.key, entry.title) for entry in entries_a] == [
        (opened_a.analysis.uid, context_a.name)
    ]
    assert [(entry.key, entry.title) for entry in entries_b] == [
        (opened_b.analysis.uid, context_b.name)
    ]


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
    workbench.response_for(
        f"ambiguity:{first.uid}"
    ).text = "Use the staff-door NFC credential."
    workbench.response_for(
        conflict.uid
    ).text = "The closing time applies to that same staff door."
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
    assert atomize_workbench_response_digest(current_workbench) == original_digest


def test_reviewed_reanalysis_rejects_two_unary_origins_for_one_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, memory = _init_context(store)
    report = impact_atomize(ctx, lambda: AggregateProvider())
    analysis = create_atomize_analysis(ctx, report)
    workbench = create_atomize_workbench(analysis)
    workbench.response_for(
        f"ambiguity:{memory.uid}"
    ).text = "The antecedent is the staff-door credential."
    workbench.response_for(
        f"atomize:{memory.uid}"
    ).text = "Retain the staff-only scope."
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
    assert atomize_workbench_response_digest(current_workbench) == original_digest


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
    assert "WHY · “same NFC” can denote a mechanism or credential" in issue_list
    assert "↳ R1 · Use the prior NFC mechanism" in issue_list
    assert "↳ R2 · Use the prior NFC credential" in issue_list
    assert "It uses the previously described NFC mechanism." not in issue_list
    assert "It uses the previously described NFC mechanism." in snapshot
    assert issue_list.count("↳ R") == 2
    assert "READING OPTIONS" not in issue_list

    saved: list[dict] = []
    with create_pipe_input() as pipe_input:
        # Open issue 1 from Items, Tab into RESPONSES, choose reading 2,
        # then move to the separate Response box and save its text.
        pipe_input.send_text(
            "\t\x1b[B\r\t\x1b[B\r\x1b[B\rNeeds the staff-only qualifier.\x13q"
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
        "Selected ordinary reading: It accepts the previously described credential."
    ) in frames[next(iter(frames))]
    assert (
        "Selected ordinary reading: Use the prior NFC credential"
        not in (frames[next(iter(frames))])
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
    assert "›   2. [ALTERNATIVE]" in expanded
    assert not any(marker in expanded for marker in ("○", "●", "◇"))
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\x1b[B\r\t\x1b[B\rq")
        run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert workbench.response_for(first.uid).selected_choice_uid.endswith(":reading:2")

    # Reopening starts on the selected reading. Entering it again clears the
    # selection, so a separate numeric "clear" command is unnecessary.
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\x1b[B\r\t\rq")
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
    assert all(not response.answered for response in workbench.responses.values())
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
        pipe_input.send_text("\t\x1b[B\r\t\x1b[B\x1b[B\rab\x7f\rq")
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
    assert "Which local reading or scope should govern this source?" in (expanded)

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
        pipe_input.send_text("\t\x1b[B\x1b[B\rq")
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
        pipe_input.send_text("\t\x1b[B\x1b[B\x1b[A\rq")
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


def test_shared_atomize_review_can_incorporate_and_apply_in_one_action():
    ctx = ops.init("workbench/materialize-todo")
    ops.add(ctx, "Use the same NFC.")
    analysis = create_atomize_analysis(ctx, impact_atomize(ctx, AggregateProvider))
    workbench = create_atomize_workbench(analysis)
    for issue in workbench.ordered_issues():
        if issue.priority == 4:
            workbench.response_for(issue.uid).text = "Use the reviewed local meaning."

    with create_pipe_input() as pipe_input:
        # Execution decisions skip the retained report and expose one compact
        # Apply row for the already reviewed responses.
        pipe_input.send_text("\x1b[B" * 99 + "\r")
        action = run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda session: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            workflow_actions=True,
        )

    assert action.kind == "INCORPORATE_AND_APPLY"


def test_applied_atomize_workbench_keeps_comments_but_removes_reapply_actions(
    monkeypatch,
):
    ctx = ops.init("workbench/already-applied")
    ops.add(ctx, "Use the same NFC.")
    analysis = create_atomize_analysis(ctx, impact_atomize(ctx, AggregateProvider))
    workbench = create_atomize_workbench(analysis)
    captured = []

    def inspect_view(view_supplier, **kwargs):
        captured.append((view_supplier(), kwargs))
        return ResolutionWorkbenchAction(kind="CLOSE")

    monkeypatch.setattr(
        "memcommit.interfaces.tui.workbenches.resolution."
        "run_resolution_workbench_shell",
        inspect_view,
    )

    returned = run_atomize_workbench_shell(
        workbench,
        analysis,
        save=lambda _session: None,
        require_tty=False,
        workflow_actions=False,
        application_complete=True,
    )

    assert returned is workbench
    view, kwargs = captured[0]
    assert view.status == "APPLIED"
    assert view.capabilities == frozenset({"SUBMIT_ITEM"})
    assert view.accept_enabled is False
    assert kwargs["review_and_apply"] is False
    assert kwargs["compact_decisions"] is False
    assert kwargs["decision_free_behavior"] == "REPORT_FIRST"
    assert kwargs["global_strategies"] == ()


def test_actionable_atomize_auto_accepts_when_no_response_is_required(
    monkeypatch,
):
    ctx = ops.init("workbench/direct-final-review")
    ops.add(ctx, "Use the same NFC.")
    analysis = create_atomize_analysis(ctx, impact_atomize(ctx, AggregateProvider))
    workbench = create_atomize_workbench(analysis)
    captured = []

    def inspect_view(view_supplier, **kwargs):
        captured.append((view_supplier(), kwargs))
        return ResolutionWorkbenchAction(kind="CLOSE")

    monkeypatch.setattr(
        "memcommit.interfaces.tui.workbenches.resolution."
        "run_resolution_workbench_shell",
        inspect_view,
    )

    run_atomize_workbench_shell(
        workbench,
        analysis,
        save=lambda _session: None,
        require_tty=False,
        workflow_actions=True,
    )

    view, kwargs = captured[0]
    assert all(item.effective_obligation == "OPTIONAL" for item in view.items)
    assert view.accept_enabled is True
    assert kwargs["review_and_apply"] is True
    assert kwargs["compact_decisions"] is True
    assert kwargs["decision_free_behavior"] == "AUTO_ACCEPT"


def test_atomize_uses_shared_save_location_frame_before_final_review():
    ctx = ops.init("workbench/destination-source")
    ops.add(ctx, "First fact. Second fact.")
    analysis = create_atomize_analysis(ctx, impact_atomize(ctx, AggregateProvider))
    workbench = create_atomize_workbench(
        analysis,
        output_context_name="workbench/destination-draft",
    )
    # A saved unary response requires incorporation, so this case remains in
    # the workbench and can exercise destination editing instead of taking the
    # decision-free local auto-apply path.
    issue = workbench.ordered_issues()[0]
    workbench.response_for(issue.uid).selected_choice_uid = issue.choice_uids[0]

    with create_pipe_input() as pipe_input:
        # Location is an ordinary Enter-activated row after the issue choices;
        # no operation-specific shortcut restores the retained report shell.
        pipe_input.send_text(
            "\x1b[B" * (len(issue.choice_uids) + 1)
            + "\r\x15workbench/destination-final\r"
        )
        action = run_atomize_workbench_shell(
            workbench,
            analysis,
            save=lambda _session: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            workflow_actions=True,
            destination=ResolutionDestination(
                value="workbench/destination-draft",
                state="NOT CREATED",
            ),
        )

    assert action.kind == "CHANGE_DESTINATION"
    assert action.destination == "workbench/destination-final"


def test_atomize_todo_materialization_creates_an_apply_ready_proposal(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _memory = _init_context(store)
    provider = AggregateProvider()
    _patch_provider(monkeypatch, provider)
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )
    findings = _finding_map(opened.analysis)
    unary = next(
        issue
        for issue in opened.workbench.ordered_issues()
        if len(findings[issue.uid].source_uids) == 1
    )
    opened.workbench.response_for(unary.uid).text = "Use this local meaning."
    store.save_atomize_workbench(opened.workbench)

    reviewed = _materialize_reviewed_workbench(
        store=store,
        context=store.load_direct(ctx.name),
        analysis=opened.analysis,
        workbench=opened.workbench,
    )
    assert reviewed.analysis.source_review_uid == opened.workbench.uid
    view = AtomizeResolutionWorkbenchAdapter(
        reviewed.analysis,
        reviewed.workbench,
    ).view()

    assert reviewed.analysis.uid != opened.analysis.uid
    assert reviewed.analysis.source_review_uid == opened.workbench.uid
    assert view.status == "READY_TO_APPLY"
    assert view.accept_enabled is True


def test_shared_atomize_apply_action_uses_the_normal_save_boundary(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _memory = _init_context(store)
    _patch_provider(monkeypatch, AggregateProvider())
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )
    findings = _finding_map(opened.analysis)
    unary = next(
        issue
        for issue in opened.workbench.ordered_issues()
        if len(findings[issue.uid].source_uids) == 1
    )
    opened.workbench.response_for(unary.uid).text = "Use this local meaning."
    store.save_atomize_workbench(opened.workbench)
    reviewed = _materialize_reviewed_workbench(
        store=store,
        context=store.load_direct(ctx.name),
        analysis=opened.analysis,
        workbench=opened.workbench,
    )
    assert reviewed.analysis.source_review_uid == opened.workbench.uid
    checkpoints_before = store.list_checkpoints(ctx.name)
    monkeypatch.setattr(
        "memcommit.commands.atomize.present_atomize_workbench",
        lambda **_kwargs: ResolutionWorkbenchAction(kind="ACCEPT"),
    )

    result = runner.invoke(
        app,
        ["atomize", "--context", ctx.name, "--output", ctx.name],
    )

    assert result.exit_code == 0, result.output
    assert "ATOMIZE APPLIED" in result.output
    assert "RECOVERY · mem undo" in result.output
    assert len(store.list_checkpoints(ctx.name)) == len(checkpoints_before) + 1
    assert store.load_direct(ctx.name).uid == ctx.uid


def test_atomize_persists_shared_destination_change_before_final_apply(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _memory = _init_context(store)
    _patch_provider(monkeypatch, AggregateProvider())
    open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
        output_context_name="workbench/old-output",
    )
    actions = iter(
        (
            ResolutionWorkbenchAction(
                kind="CHANGE_DESTINATION",
                destination="workbench/final-output",
            ),
            ResolutionWorkbenchAction(kind="ACCEPT"),
        )
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize.present_atomize_workbench",
        lambda **_kwargs: next(actions),
    )
    monkeypatch.setattr(
        "memcommit.commands.atomize._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.save_location_review.review_save_location",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError(
                "a planned Output was already reviewed in the shared workbench"
            )
        ),
    )

    result = runner.invoke(
        app,
        ["atomize", "--context", ctx.name, "--output", "workbench/old-output"],
    )

    assert result.exit_code == 0, result.output
    assert not store.context_exists("workbench/old-output")
    assert store.context_exists("workbench/final-output")
    assert store.current_context_name() == "workbench/final-output"


def test_applied_output_preview_does_not_become_a_second_session_owner(
    isolated_store,
):
    store = MemoryStore()
    source, _memory = _init_context(store)
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=source,
        provider_factory=AggregateProvider,
        output_context_name="workbench/applied-output",
    )

    applied = runner.invoke(
        app,
        [
            "atomize",
            "--context",
            source.name,
            "--save-as",
            "workbench/applied-output",
        ],
    )
    assert applied.exit_code == 0, applied.output
    output = store.load_direct("workbench/applied-output")
    output_analysis = store.load_atomize_analysis(output.uid)
    assert output_analysis is not None
    assert output_analysis.uid == opened.analysis.uid
    assert store.load_atomize_workbench(output_analysis) is None

    # Re-executing an applied Output reports the terminal state without
    # reopening a pre-Apply Viewer or persisting a second session owner.
    preview = runner.invoke(
        app,
        ["atomize", "--context", "workbench/applied-output"],
    )
    assert preview.exit_code == 0, preview.output
    assert "already applied" in preview.output
    assert store.load_atomize_workbench(output_analysis) is None

    reviewed_output = runner.invoke(
        app,
        [
            "review",
            "atomize",
            "--context",
            "workbench/applied-output",
            "--snapshot",
        ],
    )
    assert reviewed_output.exit_code == 0, reviewed_output.output
    assert "APPLIED ANALYSIS" in reviewed_output.output
    assert store.load_atomize_workbench(output_analysis) is None

    # Recover catalogs produced by the historical bug without deleting the
    # derived file: the Source terminal receipt remains the canonical owner.
    store.save_atomize_workbench(create_atomize_workbench(output_analysis))
    entries = atomize_session_entries(store)
    assert len(entries) == 1
    assert entries[0].key == opened.analysis.uid
    assert entries[0].title == source.name
    assert entries[0].status == "APPLIED"


def test_compound_atomize_action_incorporates_then_uses_normal_apply_boundary(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _memory = _init_context(store)
    _patch_provider(monkeypatch, AggregateProvider())
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )
    findings = _finding_map(opened.analysis)
    unary = next(
        issue
        for issue in opened.workbench.ordered_issues()
        if len(findings[issue.uid].source_uids) == 1
    )
    opened.workbench.response_for(unary.uid).text = "Use this local meaning."
    store.save_atomize_workbench(opened.workbench)
    checkpoints_before = store.list_checkpoints(ctx.name)
    monkeypatch.setattr(
        "memcommit.commands.atomize.present_atomize_workbench",
        lambda **_kwargs: ResolutionWorkbenchAction(
            kind="INCORPORATE_AND_APPLY",
            comment="Incorporate every saved Atomize response and apply.",
        ),
    )

    result = runner.invoke(
        app,
        ["atomize", "--context", ctx.name, "--output", ctx.name],
    )

    assert result.exit_code == 0, result.output
    assert "ATOMIZE APPLIED" in result.output
    assert "RECOVERY · mem undo" in result.output
    assert len(store.list_checkpoints(ctx.name)) == len(checkpoints_before) + 1
    checkpoint = store.list_checkpoints(ctx.name)[-1]
    assert checkpoint["args"]["source_review_uid"] == opened.workbench.uid
    assert store.load_direct(ctx.name).uid == ctx.uid


def test_unanswered_atomize_findings_apply_as_is_and_are_checkpointed(
    isolated_store,
):
    store = MemoryStore()
    ctx, _memory = _init_context(store)
    opened = open_or_create_atomize_workbench(
        store=store,
        ctx=ctx,
        provider_factory=AggregateProvider,
    )

    result = runner.invoke(app, ["atomize", "--context", ctx.name, "--save"])

    assert result.exit_code == 0, result.output
    assert "JUDGMENTS · 2 unresolved findings recorded as applied-as-is" in result.output
    checkpoint = store.list_checkpoints(ctx.name)[0]
    args = checkpoint["args"]
    assert args["application_mode"] == "AS_IS"
    assert args["unresolved_at_apply_count"] == 2
    assert {item["kind"] for item in args["unresolved_at_apply"]} == {
        "AMBIGUITY",
        "ATOMIZE_UNCERTAINTY",
    }
    assert {item["response_state"] for item in args["unresolved_at_apply"]} == {"OPEN"}
    assert args["application_workbench_uid"] == opened.workbench.uid
    assert len(args["application_workbench_response_digest"]) == 64
    assert "2 unresolved at apply" in checkpoint["description"]


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
            quality_issues=(replace(issue, readings=readings),),
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
    assert "↳ R1 · It uses the previously described NFC mechanism." in snapshot
