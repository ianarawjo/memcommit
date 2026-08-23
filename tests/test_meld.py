"""End-to-end contracts for Context-to-Context symmetric meld."""

from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from datetime import datetime, timezone
import shlex
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.config as config_module
import memcommit.commands.meld as meld_command
from memcommit.api import MemCommitClient
from memcommit.commands.endpoint_setup_flows import MeldSetupReceipt
from memcommit.atomize_grounding import (
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingSession,
    atomize_grounding_context_digest,
)
from memcommit.atomize_meld_adapter import (
    project_atomize_grounding_as_meld,
)
from memcommit.cli import app
from memcommit.comparison import (
    ComparisonInput,
    comparison_canonical_digest,
)
from memcommit.comparison_provider import (
    COMPARISON_PAYLOAD_MARKER,
    ComparisonProviderError,
    analyze_comparison,
)
from memcommit.comparison_store import (
    load_comparison_analysis,
    save_comparison_analysis,
)
from memcommit.context import Context, Memory, MemoryRef
from memcommit.config import Config
from memcommit.commands.compare import render_comparison
from memcommit.commands.meld import render_meld_session
from memcommit.commands.meld_shell import (
    MeldShellAction,
    _comparison_issue_resolution_badges,
    _line,
    run_meld_shell,
)
from memcommit.commands.resolution_workbench_shell import (
    _viewer_focus_fragments,
    RESOLUTION_WORKBENCH_STYLE,
    ResolutionGlobalStrategy,
    _seeded_report_lines,
    _seeded_report_sections,
    render_resolution_workbench_snapshot,
    resolution_seeded_report_fragments,
)
from memcommit.meld import (
    MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION,
    MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION,
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MELD_MEMORY_FOCUS_SCHEMA_VERSION,
    MeldCheckpointReceipt,
    MeldError,
    MeldSession,
    directional_comparison_basis_assessment,
    meld_canonical_digest,
    meld_accounting,
)
from memcommit.meld_provider import (
    MELD_PAYLOAD_MARKER,
    MeldProviderError,
    assess_meld_turn,
    meld_turn_request_digest,
    meld_output_schema,
)
from memcommit.meld_runtime import prepare_meld_start
from memcommit.meld_start_application import MeldStartRequest
from memcommit.update import GrantedUpdateTarget
from memcommit.meld_choice_branches import MeldChoiceBranchSet
from memcommit.responses.model import ResponseDraft
from memcommit.meld_resolution_adapter import MeldResolutionWorkbenchAdapter
from memcommit.provenance import build_trace
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
)
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)
from memcommit.study_prewarm.meld_resolution import (
    build_meld_resolution_prewarm_artifact,
    install_declared_meld_resolution_prewarms,
)
from memcommit.study_prewarm.registry import publish_artifact


runner = CliRunner()


def test_empty_meld_launcher_offers_new_session(isolated_store, monkeypatch):
    store = MemoryStore()

    class TTY:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(meld_command.sys, "stdin", TTY())
    monkeypatch.setattr(meld_command.sys, "stdout", TTY())
    monkeypatch.setattr(
        meld_command,
        "choose_session",
        lambda entries, **kwargs: (
            kwargs["new_receipt"]
            if entries == ()
            else pytest.fail("empty Meld unexpectedly had a saved row")
        ),
    )
    started = []
    monkeypatch.setattr(
        meld_command,
        "_start_new_meld_from_setup",
        lambda selected_store: started.append(selected_store),
    )

    meld_command._browse_saved_meld_sessions(store)

    assert started == [store]


def test_bare_meld_enters_setup_without_session_launcher(
    isolated_store,
    monkeypatch,
):
    started = []
    monkeypatch.setattr(
        meld_command,
        "_browse_saved_meld_sessions",
        lambda _store: pytest.fail("bare Meld must not browse saved sessions"),
    )
    monkeypatch.setattr(
        meld_command,
        "_start_new_meld_from_setup",
        lambda store: started.append(store),
    )

    result = runner.invoke(app, ["meld"])

    assert result.exit_code == 0, result.output
    assert len(started) == 1


def test_new_meld_setup_routes_directional_a_into_b(isolated_store, monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(
        meld_command,
        "choose_meld_setup",
        lambda selected_store: (
            MeldSetupReceipt("directional", "incoming", "baseline")
            if selected_store is store
            else pytest.fail("Meld setup received another store")
        ),
    )
    calls = []
    monkeypatch.setattr(meld_command, "cmd", lambda **kwargs: calls.append(kwargs))

    meld_command._start_new_meld_from_setup(store)

    assert calls == [
        {
            "left": "incoming",
            "into": "baseline",
            "left_descendants": False,
            "right_descendants": False,
        }
    ]


def test_new_meld_setup_routes_exact_memories_into_directional_command(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    monkeypatch.setattr(
        meld_command,
        "choose_meld_setup",
        lambda _store: MeldSetupReceipt(
            "directional",
            "incoming",
            "baseline",
            left_memory_uid="incoming-memory",
            right_memory_uid="baseline-memory",
        ),
    )
    calls = []
    monkeypatch.setattr(meld_command, "cmd", lambda **kwargs: calls.append(kwargs))

    meld_command._start_new_meld_from_setup(store)

    assert calls == [
        {
            "left": "incoming",
            "into": "baseline",
            "left_descendants": False,
            "right_descendants": False,
            "incoming_memory": "incoming-memory",
            "baseline_memory": "baseline-memory",
        }
    ]


class Task2Provider:
    """Deterministic Task 2 relation ledger with one grounding turn."""

    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "meld_contexts"
        assert set(output_schema["required"]) == {
            "overview",
            "paired_relations",
            "distinct_relations",
            "source_assignments",
            "issues",
            "results",
            "ready_to_apply",
        }
        assert "roughly 40-50 words at most" in prompt
        assert (
            "normally no more than roughly 40-50 words"
            in output_schema["properties"]["overview"]["description"]
        )
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        left_id = payload["frames"][0]["memories"][0]["memory_id"]
        right_id = payload["frames"][1]["memories"][0]["memory_id"]
        current = payload["current_turn"]
        if current["turn_id"] is None:
            return json.dumps(
                {
                    "overview": (
                        "Both advisors specify participant compensation, but "
                        "the rate, covered time, and payment method have "
                        "different study scopes."
                    ),
                    "relations": [
                        {
                            "relation_key": "payment_relation",
                            "left_memory_ids": [left_id],
                            "right_memory_ids": [right_id],
                            "kind": "SCOPED",
                            "status": "UNRESOLVED",
                            "summary": "Participant compensation differs.",
                            "reason": (
                                "The sources can be retained together only "
                                "after their scope and allowed methods are "
                                "settled."
                            ),
                        }
                    ],
                    "issues": [
                        {
                            "issue_key": "payment_issue",
                            "relation_keys": ["payment_relation"],
                            "priority": "REQUIRED",
                            "title": "Participant compensation policy",
                            "question": (
                                "Should the result retain the rate, travel "
                                "time, and every supported payment method?"
                            ),
                            "why_it_matters": (
                                "Choosing one advisor by order would discard "
                                "supported compensation guidance."
                            ),
                            "options": [
                                {
                                    "label": "Keep all supported options",
                                    "text": (
                                        "Retain the hourly rate, travel-time "
                                        "condition, cash, e-transfer, and an "
                                        "equivalent-value gift card."
                                    ),
                                },
                                {
                                    "label": "Preserve scoped alternatives",
                                    "text": (
                                        "Keep the in-person and online "
                                        "policies as separately scoped rules."
                                    ),
                                },
                            ],
                        }
                    ],
                    "results": [],
                    "ready_to_apply": False,
                }
            )

        assert current["scope"] in {"ALL", "ISSUE"}
        assert current["issue_ids"] == (
            ["i000001"] if current["scope"] == "ISSUE" else []
        )
        assert "Keep all" in current["comment"]
        return json.dumps(
            {
                "overview": (
                    "The grounded result retains the supported compensation "
                    "rate, covered travel time, and all payment methods "
                    "without favoring either advisor."
                ),
                "relations": [
                    {
                        "relation_key": "r000001",
                        "left_memory_ids": [left_id],
                        "right_memory_ids": [right_id],
                        "kind": "SCOPED",
                        "status": "RESOLVED",
                        "summary": (
                            "The compensation policies are complementary when "
                            "their details are retained."
                        ),
                        "reason": (
                            "The user explicitly requested that all supported "
                            "options remain available."
                        ),
                    }
                ],
                "issues": [],
                "results": [
                    {
                        "result_key": "rate",
                        "disposition": "PRESERVE",
                        "content": (
                            "Budget CAD 20–30 per hour, including "
                            "participation and applicable travel time."
                        ),
                        "reason": (
                            "The rate and travel-time condition come from Ian's policy."
                        ),
                        "relation_keys": ["r000001"],
                        "source_memory_ids": [left_id],
                        "grounded_turn_ids": [],
                    },
                    {
                        "result_key": "methods",
                        "disposition": "SYNTHESIZE",
                        "content": (
                            "Participant compensation may be paid in cash, "
                            "by e-transfer, or with an equivalent-value gift "
                            "card."
                        ),
                        "reason": (
                            "The result combines both source-supported methods "
                            "under the user's keep-all instruction."
                        ),
                        "relation_keys": ["r000001"],
                        "source_memory_ids": [left_id, right_id],
                        "grounded_turn_ids": [current["turn_id"]],
                    },
                ],
                "ready_to_apply": True,
            }
        )


class Task2CompareProvider:
    """Deterministic read-only basis for the Task 2 Meld tests."""

    def __init__(self):
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        reference_id = payload["frames"][0]["memories"][0]["memory_id"]
        compared_id = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": (
                    "Both advisors specify participant compensation, but "
                    "the rate, covered time, and payment method have "
                    "different study scopes."
                ),
                "reports": {
                    "both": "",
                    "differences": (
                        "The compensation policies differ in rate, covered "
                        "time, and supported payment methods."
                    ),
                    "reference_only": "",
                    "compared_only": "",
                },
                "relations": [
                    {
                        "relation_key": "payment_relation",
                        "reference_memory_ids": [reference_id],
                        "compared_memory_ids": [compared_id],
                        "kind": "CONFLICT",
                        "status": "UNRESOLVED",
                        "summary": "Participant compensation differs.",
                        "reason": (
                            "The sources can be retained together only after "
                            "their scope and allowed methods are settled."
                        ),
                    }
                ],
                "issues": [
                    {
                        "issue_key": "payment_issue",
                        "relation_keys": ["payment_relation"],
                        "priority": "REQUIRED",
                        "title": "Participant compensation policy",
                        "question": (
                            "Should the result retain the rate, travel time, "
                            "and every supported payment method?"
                        ),
                        "why_it_matters": (
                            "Choosing one advisor by order would discard "
                            "supported compensation guidance."
                        ),
                        "options": [
                            {
                                "label": "Keep all supported options",
                                "text": (
                                    "Retain the hourly rate, travel-time "
                                    "condition, cash, e-transfer, and an "
                                    "equivalent-value gift card."
                                ),
                            },
                            {
                                "label": "Preserve scoped alternatives",
                                "text": (
                                    "Keep the in-person and online policies "
                                    "as separately scoped rules."
                                ),
                            },
                        ],
                    }
                ],
            }
        )


class PriorityCompareProvider:
    """One REQUIRED conflict followed by one HELPFUL materialization choice."""

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        left = payload["frames"][0]["memories"]
        right = payload["frames"][1]["memories"]
        return json.dumps(
            {
                "overview": "One decision conflicts and one pair can coexist.",
                "reports": {
                    "both": "Both sources contain writing guidance.",
                    "differences": "One pair conflicts while one can coexist.",
                    "reference_only": "",
                    "compared_only": "",
                },
                "relations": [
                    {
                        "relation_key": "conflict",
                        "reference_memory_ids": [left[0]["memory_id"]],
                        "compared_memory_ids": [right[0]["memory_id"]],
                        "kind": "CONFLICT",
                        "status": "UNRESOLVED",
                        "summary": "The directives conflict.",
                        "reason": "Both cannot govern the same sentence.",
                    },
                    {
                        "relation_key": "compatible",
                        "reference_memory_ids": [left[1]["memory_id"]],
                        "compared_memory_ids": [right[1]["memory_id"]],
                        "kind": "COMPATIBLE",
                        "status": "RESOLVED",
                        "summary": "The guidance can coexist.",
                        "reason": "Each source addresses a separate detail.",
                    },
                ],
                "issues": [
                    {
                        "issue_key": "conflict_issue",
                        "relation_keys": ["conflict"],
                        "priority": "REQUIRED",
                        "title": "Choose the governing directive",
                        "question": "Which directive should govern?",
                        "why_it_matters": "The target cannot apply both.",
                        "options": [
                            {"label": "Reference", "text": "Use reference."},
                            {"label": "Compared", "text": "Use compared."},
                        ],
                    }
                ],
            }
        )


def _save_task2_comparison(
    store: MemoryStore,
    left: Context,
    right: Context,
):
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    save_comparison_analysis(
        store,
        analysis,
        expected_analysis_uid=None,
    )
    return analysis


def test_symmetric_meld_reuses_scoped_compare_descendants(isolated_store):
    store = MemoryStore()
    left = ops.init("scope/left")
    left_child = ops.init("scope/left/child")
    ops.add(left_child, "Use the short opening.")
    right = ops.init("scope/right")
    right_child = ops.init("scope/right/child")
    ops.add(right_child, "Use the long opening.")
    for context in (left, left_child, right, right_child):
        store.create_context(context)

    left_scope = meld_command._load_local_meld_source(
        store,
        left.name,
        include_descendants=True,
    )
    right_scope = meld_command._load_local_meld_source(
        store,
        right.name,
        include_descendants=True,
    )
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(
            left_scope,
            right_scope,
            reference_descendants=True,
            compared_descendants=True,
        ),
        Task2CompareProvider(),
    )
    save_comparison_analysis(
        store,
        analysis,
        expected_analysis_uid=None,
    )
    target = ops.init("scope/result")

    prepared = prepare_meld_start(
        MeldStartRequest(
            mode="SYMMETRIC",
            left_name=left.name,
            right_name=right.name,
            target_name=target.name,
            create_target=True,
            left_descendants=True,
            right_descendants=True,
        ),
        store=store,
    )
    reviewed = prepared.comparison
    assert reviewed is not None
    session = MeldSession.create_symmetric_from_comparison(reviewed, target)
    restored = MeldSession.from_dict(session.to_dict())

    assert restored.comparison_seed is not None
    assert restored.comparison_seed.analysis.include_descendants == (True, True)
    assert tuple(frame.include_descendants for frame in restored.frames) == (
        True,
        True,
    )
    assert any(
        memory.content == "Use the short opening."
        and memory.owner_context_name == "scope/left/child"
        for memory in restored.frames[0].memories
    )

    started = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            "-r",
            "--to",
            target.name,
        ],
    )
    assert started.exit_code == 0, started.output
    assert runner.invoke(app, ["switch", target.name]).exit_code == 0
    preserved = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            target.name,
            "-r",
            "--preserve-all",
        ],
    )
    assert preserved.exit_code == 0, preserved.output
    accepted = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            target.name,
            "-r",
            "--accept",
        ],
    )
    assert accepted.exit_code == 0, accepted.output
    assert len(store.load_direct(target.name).memories) == 2


def test_directional_meld_freezes_incoming_descendants_but_direct_baseline(
    isolated_store,
):
    store = MemoryStore()
    incoming = ops.init("direction/incoming")
    incoming_child = ops.init("direction/incoming/child")
    ops.add(incoming_child, "Child-owned incoming evidence.")
    baseline = ops.init("direction/baseline")
    ops.add(baseline, "Direct authoritative baseline.")
    baseline_child = ops.init("direction/baseline/child")
    ops.add(baseline_child, "Unselected child baseline.")
    for context in (incoming, incoming_child, baseline, baseline_child):
        store.create_context(context)

    incoming_scope = meld_command._load_local_meld_source(
        store,
        incoming.name,
        include_descendants=True,
        project=False,
    )
    session = MeldSession.create_directional(
        incoming_scope,
        store.load_direct(baseline.name),
        incoming_descendants=True,
        baseline_descendants=False,
    )
    restored = MeldSession.from_dict(session.to_dict())
    left, right, _target = meld_command._load_bound_contexts(store, restored)

    meld_command._assert_source_bindings(restored, left, right)
    assert restored.frames[0].include_descendants is True
    assert restored.frames[1].include_descendants is False
    assert [context.name for context in restored.frames[1].contexts or ()] == [
        baseline.name
    ]
    assert all(
        memory.owner_context_name != baseline_child.name
        for memory in restored.frames[1].memories
    )
    child_memory = next(
        memory
        for memory in restored.frames[0].memories
        if memory.owner_context_name == incoming_child.name
    )
    assert child_memory.content == "Child-owned incoming evidence."


def test_directional_compare_seed_maps_projected_descendants_to_exact_owners(
    isolated_store,
):
    store = MemoryStore()
    incoming = ops.init("direction/compare/incoming")
    incoming_child = ops.init("direction/compare/incoming/child")
    incoming_memory = ops.add(incoming_child, "Use the east entrance.")
    baseline = ops.init("direction/compare/baseline")
    baseline_child = ops.init("direction/compare/baseline/child")
    baseline_memory = ops.add(baseline_child, "Use the main entrance.")
    for context in (incoming, incoming_child, baseline, baseline_child):
        store.create_context(context)

    projected_incoming = meld_command._load_local_meld_source(
        store,
        incoming.name,
        include_descendants=True,
    )
    projected_baseline = meld_command._load_local_meld_source(
        store,
        baseline.name,
        include_descendants=True,
    )
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(
            projected_incoming,
            projected_baseline,
            reference_descendants=True,
            compared_descendants=True,
        ),
        Task2CompareProvider(),
    )
    raw_incoming = meld_command._load_local_meld_source(
        store,
        incoming.name,
        include_descendants=True,
        project=False,
    )
    raw_baseline = meld_command._load_local_meld_source(
        store,
        baseline.name,
        include_descendants=True,
        project=False,
    )

    session = MeldSession.create_directional_from_comparison(
        comparison,
        raw_incoming,
        raw_baseline,
    )
    restored = MeldSession.from_dict(session.to_dict())

    assert restored.schema_version == MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION
    assert restored.comparison_seed is not None
    assert restored.comparison_seed.analysis.uid == comparison.uid
    assert [memory.content for memory in restored.frames[0].memories] == [
        incoming_memory.content
    ]
    assert [memory.content for memory in restored.frames[1].memories] == [
        baseline_memory.content
    ]
    assert restored.frames[0].memories[0].owner_context_name == incoming_child.name
    assert restored.frames[1].memories[0].owner_context_name == baseline_child.name


def test_directional_schema_four_direct_session_remains_readable():
    incoming = ops.init("direction/v4/incoming")
    ops.add(incoming, "Incoming evidence.")
    baseline = ops.init("direction/v4/baseline")
    ops.add(baseline, "Direct baseline.")
    value = MeldSession.create_directional(incoming, baseline).to_dict()
    value["schema_version"] = 4
    for frame_value, context in zip(
        value["frames"],
        (incoming, baseline),
        strict=True,
    ):
        frame_value.pop("contexts")
        frame_value["context_digest"] = context_record_digest(context)
        for memory in frame_value["memories"]:
            memory.pop("owner_context")
    value["target"]["context_digest"] = context_record_digest(baseline)

    restored = MeldSession.from_dict(value)

    assert restored.schema_version == 4
    assert all(frame.contexts is None for frame in restored.frames)
    assert all(
        memory.owner_context_uid is None
        for frame in restored.frames
        for memory in frame.memories
    )


def test_directional_owner_aware_scopes_reject_a_shared_descendant():
    incoming = ops.init("direction/overlap/incoming")
    ops.add(incoming, "Incoming root evidence.")
    shared = ops.init("direction/overlap/shared")
    ops.add(shared, "The shared target claim.")
    incoming.add(shared)

    with pytest.raises(MeldError, match="scopes must not overlap"):
        MeldSession.create_directional(
            incoming,
            shared,
            incoming_descendants=True,
            baseline_descendants=False,
        )


def _task2_contexts(
    store: MemoryStore,
    *,
    with_comparison: bool = True,
):
    left = ops.init("ian/proposal-writing-policy")
    ops.add(
        left,
        ("Budget CAD 20–30 per hour in cash, including participation and travel time."),
    )
    right = ops.init("damien/proposal-writing-policy")
    ops.add(
        right,
        (
            "After the study, compensate participants by e-transfer or an "
            "equivalent-value gift card."
        ),
    )
    target = ops.init("jingyue/proposal-writing-policy")
    store.save(left)
    store.save(right)
    store.save(target)
    if with_comparison:
        _save_task2_comparison(store, left, right)
    store.set_current(target.name)
    return left, right, target


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr(
        "memcommit.commands.meld.connect_codex_chatgpt_provider",
        lambda: provider,
    )


def test_scripted_meld_turn_rejects_a_stale_reviewed_session(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    started = runner.invoke(app, ["meld", left.name, right.name, target.name])
    assert started.exit_code == 0, started.output
    before = store.load_meld_session(target.uid)
    assert before is not None

    result = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            target.name,
            "--issue",
            "1",
            "--choice",
            "1",
            "--expect-session",
            "0" * 64,
        ],
    )

    assert result.exit_code == 1
    assert "changed after this command was reviewed" in result.output
    assert store.load_meld_session(target.uid) == before
    assert provider.payloads == []


class DirectionalProvider:
    """One ready directional plan containing an in-place edit and an add."""

    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "meld_contexts"
        result_schema = output_schema["properties"]["results"]["items"]
        assert {"operation", "target_memory_ids"} <= set(result_schema["required"])
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        assert payload["mode"] == "DIRECTIONAL"
        assert [frame["role"] for frame in payload["frames"]] == [
            "INCOMING",
            "BASELINE",
        ]
        assert payload["target"] == {
            "context_name": "test/update/to",
            "contexts": [
                {
                    "target_context_id": "k000001",
                    "context_name": "test/update/to",
                }
            ],
            "must_remain_empty_until_acceptance": False,
            "must_remain_unchanged_until_acceptance": True,
        }
        incoming = payload["frames"][0]["memories"]
        baseline = payload["frames"][1]["memories"]
        incoming_edit = incoming[0]["memory_id"]
        incoming_add = incoming[1]["memory_id"]
        baseline_edit = baseline[0]["memory_id"]
        baseline_untouched = baseline[1]["memory_id"]
        return json.dumps(
            {
                "overview": (
                    "The incoming parking correction replaces one baseline "
                    "claim, one ATM direction is added, and the unrelated "
                    "store policy remains unchanged."
                ),
                "relations": [
                    {
                        "relation_key": "parking",
                        "left_memory_ids": [incoming_edit],
                        "right_memory_ids": [baseline_edit],
                        "kind": "CONFLICT",
                        "status": "RESOLVED",
                        "summary": "The parking access claims conflict.",
                        "reason": (
                            "Incoming evidence limits closure to the vehicle "
                            "entrance and exit."
                        ),
                    },
                    {
                        "relation_key": "atm",
                        "left_memory_ids": [incoming_add],
                        "right_memory_ids": [],
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "summary": "The incoming ATM direction is novel.",
                        "reason": "No baseline Memory contains this direction.",
                    },
                    {
                        "relation_key": "store",
                        "left_memory_ids": [],
                        "right_memory_ids": [baseline_untouched],
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "summary": "The store policy is baseline-only.",
                        "reason": "Incoming evidence does not affect it.",
                    },
                ],
                "issues": [],
                "results": [
                    {
                        "result_key": "parking_edit",
                        "operation": "EDIT",
                        "target_memory_ids": [baseline_edit],
                        "disposition": "SYNTHESIZE",
                        "content": (
                            "The underground-parking stairwell remains open; "
                            "only the vehicle entrance and exit are closed."
                        ),
                        "reason": (
                            "The incoming correction narrows the closure while "
                            "retaining the baseline subject."
                        ),
                        "relation_keys": ["parking"],
                        "source_memory_ids": [
                            incoming_edit,
                            baseline_edit,
                        ],
                        "grounded_turn_ids": [],
                    },
                    {
                        "result_key": "atm_add",
                        "operation": "ADD",
                        "target_memory_ids": [],
                        "disposition": "PRESERVE",
                        "content": (
                            "Students needing an ATM should use the nearby "
                            "Bank Annex ATM."
                        ),
                        "reason": "The incoming Context supplies a novel route.",
                        "relation_keys": ["atm"],
                        "source_memory_ids": [incoming_add],
                        "grounded_turn_ids": [],
                    },
                ],
                "ready_to_apply": True,
            }
        )


class InlineMemoryProvider:
    """Preserve one exact process-local INCOMING Memory as a baseline ADD."""

    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "meld_contexts"
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        incoming = payload["frames"][0]["memories"][0]
        baseline = payload["frames"][1]["memories"][0]
        return json.dumps(
            {
                "overview": (
                    "The inline greeting rule is a new distinction and the "
                    "existing baseline Memory remains unchanged."
                ),
                "relations": [
                    {
                        "relation_key": "inline_rule",
                        "left_memory_ids": [incoming["memory_id"]],
                        "right_memory_ids": [baseline["memory_id"]],
                        "kind": "CONFLICT",
                        "status": "RESOLVED",
                        "summary": "The inline rule replaces the prior policy.",
                        "reason": "The new exact punctuation rule is authoritative.",
                    }
                ],
                "issues": [],
                "results": [
                    {
                        "result_key": "inline_add",
                        "operation": "EDIT",
                        "target_memory_ids": [baseline["memory_id"]],
                        "disposition": "SYNTHESIZE",
                        "content": incoming["content"],
                        "reason": "Preserves the exact new greeting distinction.",
                        "relation_keys": ["inline_rule"],
                        "source_memory_ids": [
                            incoming["memory_id"],
                            baseline["memory_id"],
                        ],
                        "grounded_turn_ids": [],
                    }
                ],
                "ready_to_apply": True,
            }
        )


def test_inline_memory_meld_preserves_punctuation_without_creating_source_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    baseline = ops.init("inline/meld/baseline")
    ops.add(baseline, "Keep the existing greeting policy.")
    store.save(baseline)
    store.set_current(baseline.name)
    before_names = tuple(store.list_context_names())
    provider = InlineMemoryProvider()
    _patch_provider(monkeypatch, provider)
    content = 'all greetings need "."; keep "" and ! literal. '

    started = runner.invoke(app, ["meld", content])

    assert started.exit_code == 0, started.output
    assert "INCOMING INLINE MEMORY" in started.output
    assert len(provider.payloads) == 1
    assert provider.payloads[0]["frames"][0]["memories"][0]["content"] == content
    session = store.load_meld_session(baseline.uid)
    assert session is not None
    assert session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION
    assert session.frames[0].memories[0].content == content
    assert shlex.split(meld_command._session_command(session)) == [
        "mem",
        "meld",
        "--memory",
        content,
        "--into",
        baseline.name,
    ]
    assert tuple(store.list_context_names()) == before_names
    assert not store.context_exists("INLINE MEMORY")

    resumed = runner.invoke(app, ["meld", "--memory", content])
    assert resumed.exit_code == 0, resumed.output
    assert len(provider.payloads) == 1

    applied = runner.invoke(
        app,
        ["meld", "--memory", content, "--into", baseline.name, "--accept"],
    )
    assert applied.exit_code == 0, applied.output
    assert "MELD APPLIED" in applied.output
    assert len(provider.payloads) == 1
    current = store.load_direct(baseline.name)
    assert [memory.content for memory in current.iter_items()] == [content]
    trace = build_trace(store, current, next(iter(current.memories)))
    meld_event = next(
        event for event in trace.events if event.reason_codes[:1] == ("MELD",)
    )
    assert meld_event.kind == "EDITED"
    assert meld_event.evidence == "RECORDED"
    assert "INLINE MEMORY" in (meld_event.declared_frame or "")
    assert content in (meld_event.declared_frame or "")


def test_one_word_inline_memory_requires_explicit_memory_option(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    baseline = ops.init("inline/meld/explicit-baseline")
    ops.add(baseline, "Keep the existing greeting policy.")
    store.save(baseline)
    store.set_current(baseline.name)
    provider = InlineMemoryProvider()
    _patch_provider(monkeypatch, provider)

    missing_context = runner.invoke(app, ["meld", "hello"])
    assert missing_context.exit_code == 1
    assert "Context 'hello' does not exist" in missing_context.output
    assert provider.payloads == []

    explicit = runner.invoke(app, ["meld", "--memory", "hello"])
    assert explicit.exit_code == 0, explicit.output
    assert provider.payloads[0]["frames"][0]["memories"][0]["content"] == "hello"


def test_inline_memory_session_binds_content_to_ephemeral_context_fingerprint():
    baseline = ops.init("inline/meld/fingerprint-baseline")
    ops.add(baseline, "Keep the existing greeting policy.")
    session = MeldSession.create_directional_from_memory(
        'all greetings need "."!',
        baseline,
    )
    value = session.to_dict()
    memory = value["frames"][0]["memories"][0]
    memory["content"] = "Tampered."
    memory["content_digest"] = hashlib.sha256(b"Tampered.").hexdigest()

    with pytest.raises(MeldError, match="inline-Memory Meld"):
        MeldSession.from_dict(value)


def test_focused_directional_meld_keeps_neighbors_context_only_and_edits_selected_baseline():
    incoming = ops.init("focused/meld/incoming")
    incoming_focus = ops.add(incoming, "Only the vehicle entrance is closed.")
    incoming_neighbor = ops.add(incoming, "An ATM is available in the annex.")
    baseline = ops.init("focused/meld/baseline")
    baseline_focus = ops.add(baseline, "The parking stairwell is closed.")
    baseline_neighbor = ops.add(baseline, "The library remains open.")
    session = MeldSession.create_directional(
        incoming,
        baseline,
        incoming_memory_selector=incoming_focus.uid[:8],
        baseline_memory_selector=baseline_focus.uid[:8],
    )
    session.start_initial_analysis()
    captured = {}

    class FocusedProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "meld_contexts"
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            captured["payload"] = payload
            captured["schema"] = output_schema
            incoming_id = payload["frames"][0]["memories"][0]["memory_id"]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": (
                        "The selected incoming correction narrows the selected "
                        "baseline closure while preserving nearby policies."
                    ),
                    "relations": [
                        {
                            "relation_key": "parking",
                            "left_memory_ids": [incoming_id],
                            "right_memory_ids": [baseline_id],
                            "kind": "CONFLICT",
                            "status": "RESOLVED",
                            "summary": "The selected parking claims conflict.",
                            "reason": "The incoming claim narrows the closure.",
                        }
                    ],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "parking_edit",
                            "operation": "EDIT",
                            "target_memory_ids": [baseline_id],
                            "disposition": "SYNTHESIZE",
                            "content": (
                                "The parking stairwell remains open; only the "
                                "vehicle entrance is closed."
                            ),
                            "reason": "The incoming correction narrows the closure.",
                            "relation_keys": ["parking"],
                            "source_memory_ids": [incoming_id, baseline_id],
                            "grounded_turn_ids": [],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    assessment = assess_meld_turn(session, FocusedProvider())
    session.record_assessment(session.current_turn.uid, assessment)
    payload = captured["payload"]
    schema = captured["schema"]

    assert session.schema_version == MELD_MEMORY_FOCUS_SCHEMA_VERSION
    assert session.frames[0].selected_memory_uid == incoming_focus.uid
    assert session.frames[1].selected_memory_uid == baseline_focus.uid
    assert payload["frames"][0]["memory_focus"] is True
    assert payload["frames"][1]["memory_focus"] is True
    assert payload["frames"][0]["context_evidence"][0]["content"] == (
        incoming_neighbor.content
    )
    assert payload["frames"][1]["context_evidence"][0]["content"] == (
        baseline_neighbor.content
    )
    assert schema["properties"]["results"]["items"]["properties"][
        "operation"
    ]["enum"] == ["EDIT"]
    assert "context_id" not in json.dumps(schema)
    assert assessment.proposals[0].memory_uid == baseline_focus.uid
    assert MeldSession.from_dict(session.to_dict()).to_dict() == session.to_dict()


def test_focused_directional_meld_keeps_focus_without_neighbor_evidence():
    incoming = ops.init("focused/meld/single-incoming")
    incoming_memory = ops.add(incoming, "The visitor entrance remains open.")
    baseline = ops.init("focused/meld/single-baseline")
    baseline_memory = ops.add(baseline, "The visitor entrance remains open.")
    session = MeldSession.create_directional(
        incoming,
        baseline,
        incoming_memory_selector=incoming_memory.uid[:8],
        baseline_memory_selector=baseline_memory.uid[:8],
    )
    session.start_initial_analysis()
    captured = {}

    class SingletonFocusedProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "meld_contexts"
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            captured["payload"] = payload
            captured["schema"] = output_schema
            incoming_id = payload["frames"][0]["memories"][0]["memory_id"]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "The selected claims are already equivalent.",
                    "relations": [
                        {
                            "relation_key": "visitor_access",
                            "left_memory_ids": [incoming_id],
                            "right_memory_ids": [baseline_id],
                            "kind": "EQUIVALENT",
                            "status": "RESOLVED",
                            "summary": "Both selected claims preserve access.",
                            "reason": "Their visitor entrance policy is identical.",
                        }
                    ],
                    "issues": [],
                    "results": [],
                    "ready_to_apply": True,
                }
            )

    assessment = assess_meld_turn(session, SingletonFocusedProvider())
    session.record_assessment(session.current_turn.uid, assessment)

    assert all(frame.context_evidence == () for frame in session.frames)
    assert session.frames[0].selected_memory_uid == incoming_memory.uid
    assert session.frames[1].selected_memory_uid == baseline_memory.uid
    assert all(
        frame["memory_focus"] is True
        and "context_evidence" not in frame
        for frame in captured["payload"]["frames"]
    )
    assert captured["schema"]["properties"]["results"]["items"]["properties"][
        "operation"
    ]["enum"] == ["EDIT"]
    assert assessment.proposals == ()
    assert MeldSession.from_dict(session.to_dict()).to_dict() == session.to_dict()


class DirectionalSubtreeProvider:
    """Place one edit and one addition under exact BASELINE owners."""

    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "meld_contexts"
        required = output_schema["properties"]["results"]["items"]["required"]
        assert "target_context_id" in required
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        incoming = payload["frames"][0]["memories"]
        baseline = payload["frames"][1]["memories"]
        target_ids = {
            item["context_name"]: item["target_context_id"]
            for item in payload["target"]["contexts"]
        }
        incoming_edit, incoming_add = incoming
        baseline_edit, baseline_untouched = baseline
        return json.dumps(
            {
                "overview": (
                    "One child-owned baseline rule is corrected and one novel "
                    "incoming rule is added under another explicit child owner."
                ),
                "paired_relations": [
                    {
                        "relation_key": "access",
                        "left_memory_ids": [incoming_edit["memory_id"]],
                        "right_memory_ids": [baseline_edit["memory_id"]],
                        "kind": "CONFLICT",
                        "status": "RESOLVED",
                        "summary": "The access rules conflict.",
                        "reason": "Incoming evidence narrows the closure.",
                    }
                ],
                "distinct_relations": [
                    {
                        "relation_key": "atm",
                        "side": "LEFT",
                        "memory_ids": [incoming_add["memory_id"]],
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "summary": "The ATM guidance is new.",
                        "reason": "No baseline Memory contains it.",
                    },
                    {
                        "relation_key": "hours",
                        "side": "RIGHT",
                        "memory_ids": [baseline_untouched["memory_id"]],
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "summary": "The hours guidance is unaffected.",
                        "reason": "No incoming Memory changes it.",
                    },
                ],
                "issues": [],
                "results": [
                    {
                        "result_key": "access_edit",
                        "operation": "EDIT",
                        "target_memory_ids": [baseline_edit["memory_id"]],
                        "target_context_id": target_ids[
                            baseline_edit["owner_context_name"]
                        ],
                        "disposition": "SYNTHESIZE",
                        "content": "Only the vehicle entrance is closed.",
                        "reason": "Applies the narrower supported access scope.",
                        "relation_keys": ["access"],
                        "source_memory_ids": [incoming_edit["memory_id"]],
                        "grounded_turn_ids": [],
                    },
                    {
                        "result_key": "atm_add",
                        "operation": "ADD",
                        "target_memory_ids": [],
                        "target_context_id": target_ids[
                            baseline_untouched["owner_context_name"]
                        ],
                        "disposition": "PRESERVE",
                        "content": "Use the Annex ATM during construction.",
                        "reason": "Preserves novel incoming ATM guidance.",
                        "relation_keys": ["atm"],
                        "source_memory_ids": [incoming_add["memory_id"]],
                        "grounded_turn_ids": [],
                    },
                ],
                "ready_to_apply": True,
            }
        )


class ZeroChangeDirectionalProvider:
    """A fully equivalent directional meld with no material operations."""

    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "meld_contexts"
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        incoming = payload["frames"][0]["memories"][0]["memory_id"]
        baseline = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": (
                    "The incoming Memory is already represented exactly by "
                    "the baseline, so no material baseline change is needed."
                ),
                "relations": [
                    {
                        "relation_key": "same",
                        "left_memory_ids": [incoming],
                        "right_memory_ids": [baseline],
                        "kind": "EQUIVALENT",
                        "status": "RESOLVED",
                        "summary": "The two Memories express the same policy.",
                        "reason": "Their operational content is identical.",
                    }
                ],
                "issues": [],
                "results": [],
                "ready_to_apply": True,
            }
        )


def _directional_contexts(store: MemoryStore):
    incoming = ops.init("test/update/from")
    ops.add(
        incoming,
        (
            "The parking stairwell remains open; only the vehicle entrance "
            "and exit are closed."
        ),
    )
    ops.add(
        incoming,
        "Students needing an ATM should use the nearby Bank Annex ATM.",
    )
    baseline = ops.init("test/update/to")
    edited = ops.add(
        baseline,
        "The underground-parking stairwell is closed.",
    )
    untouched = ops.add(
        baseline,
        "The Campus Store remains open during construction.",
    )
    store.save(incoming)
    store.save(baseline)
    store.set_current(incoming.name)
    return incoming, baseline, edited, untouched


def _zero_change_directional_contexts(store: MemoryStore):
    content = "The Campus Store remains open during construction."
    incoming = ops.init("test/same/from")
    ops.add(incoming, content)
    baseline = ops.init("test/same/to")
    memory = ops.add(baseline, content)
    store.save(incoming)
    store.save(baseline)
    store.set_current(incoming.name)
    return incoming, baseline, memory


class DirectionalCompareEchoProvider:
    """Materialize only from the frozen ordered Compare basis."""

    def __init__(self):
        self.payloads: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "meld_contexts"
        assert "exact reviewed ordered INCOMING-to-BASELINE Compare" in prompt
        assert set(output_schema["properties"]) == {
            "overview",
            "additional_issues",
            "results",
            "ready_to_apply",
        }
        assert "paired_relations" not in output_schema["properties"]
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        basis = payload["comparison_basis"]
        return json.dumps(
            {
                "overview": (
                    "The reviewed Compare ledger is retained while the "
                    "directional target remains unresolved."
                ),
                "additional_issues": [],
                "results": basis["results"],
                "ready_to_apply": basis["ready_to_apply"],
            }
        )


def test_directional_command_uses_exact_saved_compare_basis(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming = ops.init("direction/compare-command/incoming")
    ops.add(incoming, "Pay participants in cash.")
    baseline = ops.init("direction/compare-command/baseline")
    ops.add(baseline, "Pay participants by e-transfer.")
    store.save(incoming)
    store.save(baseline)
    comparison = _save_task2_comparison(store, incoming, baseline)
    provider = DirectionalCompareEchoProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name],
    )

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 1
    assert provider.payloads[0]["comparison_basis"]["paired_relations"]
    session = store.load_meld_session(baseline.uid)
    assert session is not None
    assert session.schema_version == MELD_DIRECTIONAL_COMPARISON_SCHEMA_VERSION
    assert session.comparison_seed is not None
    assert session.comparison_seed.analysis.uid == comparison.uid
    assert [relation.uid for relation in session.current_assessment.relations] == [
        relation.uid for relation in comparison.relations
    ]
    assert "MELD NEEDS INPUT · DIRECTIONAL" in result.output
    assert f"IMPACT · mem impact meld --session {session.uid}" in result.output


def test_directional_compare_seed_output_cannot_restate_relation_drift():
    incoming = ops.init("direction/compare-drift/incoming")
    ops.add(incoming, "Pay participants in cash.")
    baseline = ops.init("direction/compare-drift/baseline")
    ops.add(baseline, "Pay participants by e-transfer.")
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(incoming, baseline),
        Task2CompareProvider(),
    )
    session = MeldSession.create_directional_from_comparison(
        comparison,
        incoming,
        baseline,
    )
    session.start_initial_analysis()

    class DriftedCompareProvider(DirectionalCompareEchoProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            value = json.loads(
                super().complete(
                    prompt,
                    operation=operation,
                    output_schema=output_schema,
                )
            )
            value["paired_relations"] = [
                {"summary": "A rewritten judgment."}
            ]
            return json.dumps(value)

    with pytest.raises(
        MeldProviderError,
        match="directional comparison meld response",
    ):
        assess_meld_turn(session, DriftedCompareProvider())


def test_directional_compare_seed_restores_mixed_relation_order():
    incoming = ops.init("direction/compare-order/incoming")
    left_one = ops.add(incoming, "Use the north entrance.")
    left_two = ops.add(incoming, "Pay participants in cash.")
    baseline = ops.init("direction/compare-order/baseline")
    right_one = ops.add(baseline, "Pay participants by e-transfer.")
    right_two = ops.add(baseline, "The library closes at 9 p.m.")

    class MixedOrderCompareProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "compare_contexts"
            payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
            left = payload["frames"][0]["memories"]
            right = payload["frames"][1]["memories"]
            return json.dumps(
                {
                    "overview": "One incoming claim is distinct, one conflicts, and one baseline claim is distinct.",
                    "reports": {
                        "both": "",
                        "differences": "Only the payment guidance conflicts.",
                        "reference_only": "The entrance guidance is incoming-only.",
                        "compared_only": "The closing time is baseline-only.",
                    },
                    "relations": [
                        {
                            "relation_key": "incoming_distinct",
                            "reference_memory_ids": [left[0]["memory_id"]],
                            "compared_memory_ids": [],
                            "kind": "DISTINCT",
                            "status": "RESOLVED",
                            "summary": "Entrance guidance appears only in incoming.",
                            "reason": "No baseline Memory covers entrance access.",
                        },
                        {
                            "relation_key": "payment_conflict",
                            "reference_memory_ids": [left[1]["memory_id"]],
                            "compared_memory_ids": [right[0]["memory_id"]],
                            "kind": "SCOPED",
                            "status": "RESOLVED",
                            "summary": "Payment methods conflict.",
                            "reason": "The two methods govern the same payment.",
                        },
                        {
                            "relation_key": "baseline_distinct",
                            "reference_memory_ids": [],
                            "compared_memory_ids": [right[1]["memory_id"]],
                            "kind": "DISTINCT",
                            "status": "RESOLVED",
                            "summary": "Closing time appears only in baseline.",
                            "reason": "No incoming Memory changes the closing time.",
                        },
                    ],
                    "issues": [],
                }
            )

    comparison = analyze_comparison(
        ComparisonInput.from_contexts(incoming, baseline),
        MixedOrderCompareProvider(),
    )
    session = MeldSession.create_directional_from_comparison(
        comparison,
        incoming,
        baseline,
    )
    session.start_initial_analysis()

    assessment = assess_meld_turn(session, DirectionalCompareEchoProvider())
    basis = directional_comparison_basis_assessment(
        comparison,
        (session.frames[0], session.frames[1]),
    )

    assert [relation.uid for relation in assessment.relations] == [
        relation.uid for relation in basis.relations
    ]
    assert [relation.kind for relation in assessment.relations] == [
        relation.kind for relation in basis.relations
    ]
    assert [relation.to_dict() for relation in assessment.relations] == [
        relation.to_dict() for relation in basis.relations
    ]
    assert {relation.kind for relation in assessment.relations} == {
        "DISTINCT",
        "SCOPED",
    }
    assert {left_one.uid, left_two.uid, right_one.uid, right_two.uid} == {
        member.memory_uid
        for relation in assessment.relations
        for member in relation.members
    }


def test_compare_seed_adds_stable_helpful_materialization_after_required():
    left = ops.init("left/priorities")
    ops.add(left, "Use the short opening.")
    ops.add(left, "Show the workflow as a diagram.")
    right = ops.init("right/priorities")
    ops.add(right, "Use the long opening.")
    ops.add(right, "List the workflow steps in order.")
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        PriorityCompareProvider(),
    )

    first = MeldSession.create_symmetric_from_comparison(
        comparison,
        ops.init("target/priorities-one"),
    )
    second = MeldSession.create_symmetric_from_comparison(
        comparison,
        ops.init("target/priorities-two"),
    )

    issues = first.current_assessment.issues
    assert [issue.priority for issue in issues] == ["REQUIRED", "HELPFUL"]
    assert issues[0].uid == comparison.issues[0].uid
    assert issues[1].relation_uids == (comparison.relations[1].uid,)
    assert [option.label for option in issues[1].options] == [
        "Keep separately",
        "Combine if lossless",
    ]
    assert issues[1].uid == second.current_assessment.issues[1].uid
    assert meld_accounting(first).required_issues == 1
    assert meld_accounting(first).helpful_issues == 1
    assert "[HELPFUL] Compatible · The guidance can coexist." in (
        render_meld_session(first)
    )

    legacy_value = first.to_dict()
    legacy_value["schema_version"] = 2
    legacy_value["turns"][0]["assessment"]["issues"] = [
        issue.to_dict() for issue in comparison.issues
    ]
    restored_legacy = MeldSession.from_dict(legacy_value)
    assert restored_legacy.schema_version == 2
    assert [issue.uid for issue in restored_legacy.current_assessment.issues] == [
        issue.uid for issue in comparison.issues
    ]


def test_seeded_meld_report_uses_nested_cards_and_blue_selection_badges():
    left = ops.init("left/report-cards")
    ops.add(left, "Use the short opening.")
    right = ops.init("right/report-cards")
    ops.add(right, "Use the long opening.")
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(
        comparison,
        ops.init("target/report-cards"),
    )
    view = MeldResolutionWorkbenchAdapter(session).view()
    item = view.items[0]
    report = render_comparison(
        comparison,
        reused=True,
        durable=True,
    ).partition("\nThe complete source-linked relation ledger")[0]
    conflict_section = next(
        index
        for index, (_offset, key) in enumerate(
            _seeded_report_sections(_seeded_report_lines(view, report, (), True, False))
        )
        if key == "ITEM:0"
    )

    fragments = resolution_seeded_report_fragments(
        view,
        report,
        strategies=(
            ResolutionGlobalStrategy(
                label="Preserve remaining helpful items",
                action_kind="SUBMIT_ALL",
                comment="Preserve the remaining helpful items.",
            ),
        ),
        drafts={item.uid: ResponseDraft(item.options[0].uid, "")},
        focused_section=conflict_section,
        review_and_apply=True,
    )
    rendered = "".join(text for _style, text in fragments)

    assert "╭─ MEM COMPARE · SYMMETRIC PEERS" in rendered
    assert "CONTEXT LOCATIONS" in rendered
    assert "SOURCE A · left/report-cards" in rendered
    assert "SOURCE B · right/report-cards" in rendered
    assert "RESULT · target/report-cards" in rendered
    assert rendered.index("CONTEXT LOCATIONS") < rendered.index("WHAT MEM UNDERSTOOD")
    assert "╭─ WHAT MEM UNDERSTOOD" in rendered
    assert "╭─ POTENTIAL CONFLICTS · 1 → 1" in rendered
    assert "│   CONFLICT 1" in rendered
    assert "│ ╭─ CONFLICT 1" not in rendered
    assert "SELECTED · Keep all supported options" in rendered
    assert "POLICY · Preserve remaining helpful items" in rendered
    assert any(
        style == "class:selection-badge" and "SELECTED ·" in text
        for style, text in fragments
    )
    assert any(
        style == "class:detail-card" and "compensation" in text.lower()
        for style, text in fragments
    )
    assert any(
        style == "class:viewer-section" and "CONFLICT 1" in text
        for style, text in fragments
    )

    resolved_fragments = resolution_seeded_report_fragments(
        view,
        report,
        report_item_badges=(
            "KEPT BOTH · Keep all supported options + Preserve scoped alternatives",
        ),
        report_conflicts_remaining=0,
        review_and_apply=True,
    )
    resolved = "".join(text for _style, text in resolved_fragments)
    assert "POTENTIAL CONFLICTS · 1 → 0" in resolved
    assert "KEPT BOTH · Keep all supported options + Preserve scoped" in resolved
    assert "alternatives" in resolved
    assert any(
        style == "class:selection-badge" and "KEPT BOTH ·" in text
        for style, text in resolved_fragments
    )


def test_resolution_badges_show_direct_and_synthesized_content():
    def ready_session(comment: str) -> MeldSession:
        left = ops.init(f"left/badge-{len(comment)}")
        ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
        right = ops.init(f"right/badge-{len(comment)}")
        ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
        comparison = analyze_comparison(
            ComparisonInput.from_contexts(left, right),
            Task2CompareProvider(),
        )
        session = MeldSession.create_symmetric_from_comparison(
            comparison,
            ops.init(f"target/badge-{len(comment)}"),
        )
        issue_uid = session.current_assessment.issues[0].uid
        turn = session.start_turn(
            comment,
            scope="ISSUE",
            issue_uids=(issue_uid,),
        )
        session.record_assessment(
            turn.uid,
            assess_meld_turn(session, Task2Provider()),
        )
        return session

    direct = ready_session(
        "Keep all supported details while maintaining the original word count."
    )
    assert _comparison_issue_resolution_badges(direct) == (
        "OTHER DIRECTION · Keep all supported details while maintaining the original word count.",
    )

    synthesized = ready_session("Keep all supported details.")
    synthesized.turns = synthesized.turns[:-1] + (
        replace(synthesized.turns[-1], issue_uids=()),
    )
    assert _comparison_issue_resolution_badges(synthesized) == (
        "COMBINED · Participant compensation may be paid in cash, by e-transfer, or with an…",
    )


def test_result_rows_share_tree_prefix_and_keep_apply_card_fully_anchored():
    left = ops.init("left/result-tree-row")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("right/result-tree-row")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(
        comparison,
        ops.init("target/result-tree-row"),
    )
    issue_uid = session.current_assessment.issues[0].uid
    turn = session.start_turn(
        "Keep all supported details.",
        scope="ISSUE",
        issue_uids=(issue_uid,),
    )
    session.record_assessment(turn.uid, assess_meld_turn(session, Task2Provider()))
    view = MeldResolutionWorkbenchAdapter(session).view()
    report = render_comparison(
        comparison,
        reused=True,
        durable=True,
    ).partition("\nThe complete source-linked relation ledger")[0]
    sections = _seeded_report_sections(
        _seeded_report_lines(view, report, (), True, False)
    )
    result_section = next(
        index for index, (_offset, key) in enumerate(sections) if key == "RESULT:0"
    )
    result_fragments = resolution_seeded_report_fragments(
        view,
        report,
        focused_section=result_section,
        review_and_apply=True,
    )
    assert any(
        style == "class:memory-object.focused"
        and "›     +" in text
        and "[PRESERVE]" in text
        for style, text in result_fragments
    )
    assert any(
        style == "class:memory-object.focused" and "WHY ·" in text
        for style, text in result_fragments
    )
    result_anchor = next(
        index
        for index, (style, _text) in enumerate(result_fragments)
        if style == "[SetCursorPosition]"
    )
    result_body_end = max(
        index
        for index, (style, _text) in enumerate(result_fragments)
        if style == "class:memory-object.focused"
    )
    assert result_anchor > result_body_end

    apply_fragments = resolution_seeded_report_fragments(
        view,
        report,
        strategies=(
            ResolutionGlobalStrategy(
                label="This materialization policy is no longer actionable",
                action_kind="SUBMIT_ALL",
                comment="Preserve remaining results.",
            ),
        ),
        focused_section=len(sections) - 1,
        review_and_apply=True,
    )
    anchor_index = next(
        index
        for index, (style, _text) in enumerate(apply_fragments)
        if style == "[SetCursorPosition]"
    )
    apply_bottom = max(
        index for index, (_style, text) in enumerate(apply_fragments) if "╰" in text
    )
    assert anchor_index > apply_bottom
    assert all(
        "This materialization policy is no longer actionable" not in text
        for _style, text in apply_fragments
    )


def test_viewer_position_is_blue_only_while_viewer_has_focus():
    fragments = [
        ("[SetCursorPosition]", ""),
        ("class:viewer-section", "MEM COMPARE"),
        ("class:detail-card.focused", "Focused conflict"),
        ("class:memory-object.focused", "Focused Memory"),
        ("class:option-card.focused", "Option cursor"),
        ("class:option-card.other", "Other-direction cursor"),
        ("class:selection-badge", "CHOSEN · Two sentences"),
        ("class:option-card.selected", "Durable selected option"),
    ]
    assert _viewer_focus_fragments(fragments, focused=True) is fragments
    assert _viewer_focus_fragments(fragments, focused=False) == [
        ("[SetCursorPosition]", ""),
        ("class:section", "MEM COMPARE"),
        ("class:detail-card", "Focused conflict"),
        ("class:memory-object", "Focused Memory"),
        ("class:option-card", "Option cursor"),
        ("class:option-card", "Other-direction cursor"),
        ("class:selection-badge", "CHOSEN · Two sentences"),
        ("class:option-card.selected", "Durable selected option"),
    ]


def test_compare_report_is_white_and_only_memory_objects_are_lavender():
    report = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str("class:detail-card")
    memory = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str("class:memory-object")

    assert report.color == "ffffff"
    assert memory.color == "cad3f5"


def test_v3_rejects_cross_relation_thematic_compression():
    left = ops.init("left/no-compression")
    ops.add(left, "Use the short opening.")
    ops.add(left, "Show the workflow as a diagram.")
    right = ops.init("right/no-compression")
    ops.add(right, "Use the long opening.")
    ops.add(right, "List the workflow steps in order.")
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        PriorityCompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(
        comparison,
        ops.init("target/no-compression"),
    )
    session.start_turn(
        "Use one broad result for all writing guidance.",
        scope="ALL",
    )

    class CompressedProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            relations = [
                *payload["previous"]["paired_relations"],
                *[
                    {
                        "relation_key": relation["relation_key"],
                        "left_memory_ids": (
                            relation["memory_ids"]
                            if relation["side"] == "LEFT"
                            else []
                        ),
                        "right_memory_ids": (
                            relation["memory_ids"]
                            if relation["side"] == "RIGHT"
                            else []
                        ),
                        "kind": "DISTINCT",
                        "status": relation["status"],
                        "summary": relation["summary"],
                        "reason": relation["reason"],
                    }
                    for relation in payload["previous"]["distinct_relations"]
                ],
            ]
            source_ids = [
                memory["memory_id"]
                for frame in payload["frames"]
                for memory in frame["memories"]
            ]
            return json.dumps(
                {
                    "overview": "All guidance is compressed into one result.",
                    "relations": [
                        {**relation, "status": "RESOLVED"} for relation in relations
                    ],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "compressed",
                            "disposition": "SYNTHESIZE",
                            "content": "Use concise text and a clear workflow.",
                            "reason": "The themes concern proposal writing.",
                            "relation_keys": [
                                relation["relation_key"] for relation in relations
                            ],
                            "source_memory_ids": source_ids,
                            "grounded_turn_ids": [payload["current_turn"]["turn_id"]],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    assessment = assess_meld_turn(session, CompressedProvider())
    with pytest.raises(MeldError, match="exactly one primary relation"):
        session.record_assessment(session.current_turn.uid, assessment)


def test_context_meld_one_shot_reply_resume_and_provider_free_apply(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    left_before = store._context_file(left.name).read_bytes()
    right_before = store._context_file(right.name).read_bytes()
    target_before = store._context_file(target.name).read_bytes()

    initial = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name],
    )
    assert initial.exit_code == 0, initial.output
    assert len(provider.payloads) == 0
    assert "MELD NEEDS INPUT · SYMMETRIC" in initial.output
    assert store._context_file(target.name).read_bytes() == target_before
    assert store.list_checkpoints(target.name) == []
    comparison = load_comparison_analysis(left.uid, right.uid)
    session = store.load_meld_session(target.uid)
    assert comparison is not None
    assert session is not None
    assert session.comparison_seed is not None
    assert session.comparison_seed.analysis.uid == comparison.uid
    assert session.comparison_seed.analysis_digest == (
        comparison_canonical_digest(comparison.to_dict())
    )
    impact = runner.invoke(app, ["impact", "meld", "--session", session.uid])
    assert impact.exit_code == 0, impact.output
    assert "MEM COMPARE · SYMMETRIC PEERS" in impact.output
    assert "Participant compensation policy" in impact.output
    assert [frame.uid for frame in session.frames] == [
        frame.uid for frame in comparison.frames
    ]
    assert [relation.uid for relation in session.current_assessment.relations] == [
        relation.uid for relation in comparison.relations
    ]
    assert [issue.uid for issue in session.current_assessment.issues] == [
        issue.uid for issue in comparison.issues
    ]
    assert [
        option.uid
        for issue in session.current_assessment.issues
        for option in issue.options
    ] == [option.uid for issue in comparison.issues for option in issue.options]

    resumed = runner.invoke(app, ["meld", left.name, right.name, target.name])
    assert resumed.exit_code == 0, resumed.output
    assert len(provider.payloads) == 0
    assert "Resumed without calling the semantic provider" in resumed.output

    grounded = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            target.name,
            "--issue",
            "1",
            "--choice",
            "1",
            "--comment",
            "Keep all of these payment options.",
        ],
    )
    assert grounded.exit_code == 0, grounded.output
    assert len(provider.payloads) == 1
    assert "MELD READY · SYMMETRIC" in grounded.output
    assert store._context_file(target.name).read_bytes() == target_before
    ready_session = store.load_meld_session(target.uid)
    grounded_impact = runner.invoke(
        app, ["impact", "meld", "--session", ready_session.uid]
    )
    assert grounded_impact.exit_code == 0, grounded_impact.output
    assert "CAD 20–30" in grounded_impact.output
    assert "cash" in grounded_impact.output
    assert "e-transfer" in grounded_impact.output
    assert "gift card" in grounded_impact.output
    assert _comparison_issue_resolution_badges(ready_session) == (
        "CHOSEN · Keep all supported options",
    )
    ready_view = MeldResolutionWorkbenchAdapter(ready_session).view()
    ready_report = render_comparison(
        comparison,
        reused=True,
        durable=True,
    ).partition("\nThe complete source-linked relation ledger")[0]
    ready_sections = _seeded_report_sections(
        _seeded_report_lines(ready_view, ready_report, (), True, False)
    )
    assert sum(key.startswith("RESULT:") for _offset, key in ready_sections) == 2
    assert ready_sections[-1][1] == "RESOLVE_ALL"

    applied = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--accept"],
    )
    assert applied.exit_code == 0, applied.output
    assert len(provider.payloads) == 1
    assert "MELD APPLIED · SYMMETRIC" in applied.output
    assert "RESULT MEMORIES · 2" in applied.output
    current = store.load_direct(target.name)
    assert [memory.content for memory in current.iter_items()] == [
        (
            "Budget CAD 20–30 per hour, including participation and "
            "applicable travel time."
        ),
        (
            "Participant compensation may be paid in cash, by e-transfer, "
            "or with an equivalent-value gift card."
        ),
    ]
    checkpoints = store.list_checkpoints(target.name)
    assert len(checkpoints) == 1
    assert checkpoints[0]["command"] == "meld"
    assert (
        checkpoints[0]["args"]["meld"]["change_set"]["digest"]
        == checkpoints[0]["args"]["meld"]["change_set_digest"]
    )
    assert store._context_file(left.name).read_bytes() == left_before
    assert store._context_file(right.name).read_bytes() == right_before
    trace = build_trace(store, current, next(iter(current.memories)))
    meld_event = next(event for event in trace.events if event.kind == "MELDED")
    assert meld_event.evidence == "RECORDED"
    assert meld_event.reason_codes[:1] == ("MELD",)
    assert "ian/proposal-writing-policy" in (meld_event.declared_frame or "")
    assert "Budget CAD 20–30 per hour in cash" in (meld_event.declared_frame or "")

    second_accept = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--accept"],
    )
    assert second_accept.exit_code == 0
    assert "prior application recovered; no duplicate write" in second_accept.output
    assert len(store.list_checkpoints(target.name)) == 1
    assert len(provider.payloads) == 1


def test_undo_and_redo_restore_meld_application_state_as_one_operation(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)

    assert (
        runner.invoke(app, ["meld", left.name, right.name, target.name]).exit_code
        == 0
    )
    grounded = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            target.name,
            "--issue",
            "1",
            "--choice",
            "1",
            "--comment",
            "Keep all supported details.",
        ],
    )
    assert grounded.exit_code == 0, grounded.output
    applied = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--accept"],
    )
    assert applied.exit_code == 0, applied.output
    applied_session = store.load_meld_session(target.uid)
    assert applied_session.state == "APPLIED"
    assert applied_session.application is not None
    original_checkpoint_uid = applied_session.application.checkpoint_uid
    assert len(store.load_direct(target.name).memories) == 2

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert "Undid command: mem meld" in undone.output
    assert not store.load_direct(target.name).memories
    undone_session = store.load_meld_session(target.uid)
    assert undone_session.state == "READY_TO_APPLY"
    assert undone_session.application is None

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert "Redid command: mem meld" in redone.output
    assert len(store.load_direct(target.name).memories) == 2
    redone_session = store.load_meld_session(target.uid)
    assert redone_session.state == "APPLIED"
    assert redone_session.application is not None
    assert redone_session.application.checkpoint_uid == original_checkpoint_uid
    assert [entry["command"] for entry in store.list_checkpoints(target.name)[:3]] == [
        "redo",
        "undo",
        "meld",
    ]

    undone_again = runner.invoke(app, ["undo"])
    assert undone_again.exit_code == 0, undone_again.output
    assert not store.load_direct(target.name).memories
    assert store.load_meld_session(target.uid).state == "READY_TO_APPLY"


def test_symmetric_meld_creates_missing_compare_without_switching_current(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(
        store,
        with_comparison=False,
    )

    provider = Task2CompareProvider()
    monkeypatch.setattr(
        "memcommit.commands.meld.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    current_before = store.current_context_name()

    result = runner.invoke(app, ["meld", left.name, right.name, target.name])

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 1
    analysis = load_comparison_analysis(left.uid, right.uid)
    assert analysis is not None
    session = store.load_meld_session(target.uid)
    assert session is not None
    assert session.comparison_seed is not None
    assert session.comparison_seed.analysis.uid == analysis.uid
    assert store.current_context_name() == current_before


def test_symmetric_meld_refreshes_stale_compare(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    prior = load_comparison_analysis(left.uid, right.uid)
    assert prior is not None
    provider = Task2CompareProvider()
    monkeypatch.setattr(
        "memcommit.commands.meld.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    changed = store.load_direct(left.name)
    memory = next(iter(changed.iter_items()))
    changed.replace(
        type(memory)(
            uid=memory.uid,
            content="The compensation policy changed after Compare.",
        )
    )
    store.save(changed)

    stale = runner.invoke(app, ["meld", left.name, right.name, target.name])

    assert stale.exit_code == 0, stale.output
    assert len(provider.payloads) == 1
    refreshed = load_comparison_analysis(left.uid, right.uid)
    assert refreshed is not None
    assert refreshed.uid != prior.uid
    session = store.load_meld_session(target.uid)
    assert session is not None
    assert session.comparison_seed is not None
    assert session.comparison_seed.analysis.uid == refreshed.uid


def test_symmetric_meld_creates_exact_order_when_only_reverse_exists(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store, with_comparison=False)
    reverse = _save_task2_comparison(store, right, left)
    provider = Task2CompareProvider()
    monkeypatch.setattr(
        "memcommit.commands.meld.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["meld", left.name, right.name, target.name])

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 1
    forward = load_comparison_analysis(left.uid, right.uid)
    assert forward is not None
    assert forward.uid != reverse.uid
    assert load_comparison_analysis(right.uid, left.uid).uid == reverse.uid
    session = store.load_meld_session(target.uid)
    assert session is not None
    assert session.comparison_seed is not None
    assert session.comparison_seed.analysis.uid == forward.uid


def test_seeded_meld_schema_round_trips_and_rejects_tampering(
    isolated_store,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    comparison = load_comparison_analysis(left.uid, right.uid)
    assert comparison is not None
    session = MeldSession.create_symmetric_from_comparison(
        comparison,
        target,
    )

    value = session.to_dict()
    restored = MeldSession.from_dict(value)

    assert value["schema_version"] == 3
    assert restored.to_dict() == value
    legacy = MeldSession.create_symmetric(left, right, target).to_dict()
    assert legacy["schema_version"] == 1
    assert "comparison_seed" not in legacy
    assert MeldSession.from_dict(legacy).to_dict() == legacy

    bad_digest = json.loads(json.dumps(value))
    bad_digest["comparison_seed"]["analysis_digest"] = "0" * 64
    with pytest.raises(MeldError, match="digest does not match"):
        MeldSession.from_dict(bad_digest)

    bad_import = json.loads(json.dumps(value))
    bad_import["turns"][0]["assessment"]["relations"][0]["summary"] = (
        "A forged imported relation."
    )
    with pytest.raises(MeldError, match="turn zero does not match"):
        MeldSession.from_dict(bad_import)


def test_directional_meld_uses_current_incoming_and_relative_baseline(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, _, _ = _directional_contexts(store)
    provider = DirectionalProvider()
    _patch_provider(monkeypatch, provider)
    incoming_before = store._context_file(incoming.name).read_bytes()
    baseline_before = store._context_file(baseline.name).read_bytes()

    result = runner.invoke(app, ["meld", "--into", "../to"])

    assert result.exit_code == 0, result.output
    assert "MELD READY · DIRECTIONAL" in result.output
    assert (
        "INCOMING test/update/from → BASELINE / TARGET test/update/to"
    ) in result.output
    assert len(provider.payloads) == 1
    assert [frame["context_name"] for frame in provider.payloads[0]["frames"]] == [
        incoming.name,
        baseline.name,
    ]
    assert store._context_file(incoming.name).read_bytes() == incoming_before
    assert store._context_file(baseline.name).read_bytes() == baseline_before
    assert store.list_checkpoints(baseline.name) == []
    session = store.load_meld_session(baseline.uid)
    assert session is not None
    assert session.mode == "DIRECTIONAL"
    assert [frame.role for frame in session.frames] == [
        "INCOMING",
        "BASELINE",
    ]


def test_directional_meld_from_uses_current_baseline_and_canonical_session(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, _, _ = _directional_contexts(store)
    store.set_current(baseline.name)
    provider = DirectionalProvider()
    _patch_provider(monkeypatch, provider)

    shorthand = runner.invoke(app, ["meld", "--from", "../from"])

    assert shorthand.exit_code == 0, shorthand.output
    assert (
        "INCOMING test/update/from → BASELINE / TARGET test/update/to"
    ) in shorthand.output
    assert "MELD READY · DIRECTIONAL" in shorthand.output
    first_session = store.load_meld_session(baseline.uid)
    assert first_session is not None
    assert [frame.context_name for frame in first_session.frames] == [
        incoming.name,
        baseline.name,
    ]
    assert len(provider.payloads) == 1

    canonical = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name],
    )

    assert canonical.exit_code == 0, canonical.output
    resumed_session = store.load_meld_session(baseline.uid)
    assert resumed_session is not None
    assert resumed_session.uid == first_session.uid
    assert len(provider.payloads) == 1


def test_directional_meld_edits_adds_and_preserves_baseline_then_recovers(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, edited, untouched = _directional_contexts(store)
    provider = DirectionalProvider()
    _patch_provider(monkeypatch, provider)
    incoming_before = store._context_file(incoming.name).read_bytes()

    initial = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name],
    )
    assert initial.exit_code == 0, initial.output
    assert "MELD READY · DIRECTIONAL" in initial.output
    assert store.list_checkpoints(baseline.name) == []

    applied = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )

    assert applied.exit_code == 0, applied.output
    assert "MELD APPLIED · DIRECTIONAL" in applied.output
    assert "EFFECTS · ADD 1 · EDIT 1" in applied.output
    current = store.load_direct(baseline.name)
    memories = tuple(current.iter_items())
    assert [memory.uid for memory in memories[:2]] == [
        edited.uid,
        untouched.uid,
    ]
    assert [memory.content for memory in memories] == [
        (
            "The underground-parking stairwell remains open; only the "
            "vehicle entrance and exit are closed."
        ),
        "The Campus Store remains open during construction.",
        "Students needing an ATM should use the nearby Bank Annex ATM.",
    ]
    assert store._context_file(incoming.name).read_bytes() == incoming_before
    checkpoints = store.list_checkpoints(baseline.name)
    assert len(checkpoints) == 1
    record = checkpoints[0]["args"]["meld"]
    assert record["schema_version"] == 3
    assert record["mode"] == "DIRECTIONAL"
    assert [source["role"] for source in record["sources"]] == [
        "INCOMING",
        "BASELINE",
    ]
    assert [result["operation"] for result in record["results"]] == [
        "EDIT",
        "ADD",
    ]

    repeated = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )

    assert repeated.exit_code == 0, repeated.output
    assert "prior application recovered; no duplicate write" in repeated.output
    assert len(store.list_checkpoints(baseline.name)) == 1
    assert len(provider.payloads) == 1

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert store.load_meld_session(baseline.uid).state == "READY_TO_APPLY"
    assert [
        memory.content for memory in store.load_direct(baseline.name).memories.values()
    ] == [
        "The underground-parking stairwell is closed.",
        "The Campus Store remains open during construction.",
    ]

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert store.load_meld_session(baseline.uid).state == "APPLIED"


def test_directional_meld_applies_descendants_to_exact_owners_as_one_command(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming = ops.init("directional-tree/incoming")
    incoming_access = ops.init("directional-tree/incoming/access")
    ops.add(incoming_access, "Only the vehicle entrance is closed.")
    incoming_atm = ops.init("directional-tree/incoming/atm")
    ops.add(incoming_atm, "Use the Annex ATM during construction.")
    baseline = ops.init("directional-tree/baseline")
    baseline_access = ops.init("directional-tree/baseline/access")
    edited = ops.add(baseline_access, "The parking area is fully closed.")
    baseline_hours = ops.init("directional-tree/baseline/hours")
    retained = ops.add(baseline_hours, "The Campus Store closes at 6 p.m.")
    for context in (
        incoming,
        incoming_access,
        incoming_atm,
        baseline,
        baseline_access,
        baseline_hours,
    ):
        store.create_context(context)
    provider = DirectionalSubtreeProvider()
    _patch_provider(monkeypatch, provider)
    scoped_baseline = meld_command._load_local_meld_source(
        store,
        baseline.name,
        include_descendants=True,
        project=False,
    )
    assert [
        item.name for item in scoped_baseline.iter_items() if isinstance(item, Context)
    ] == [baseline_access.name, baseline_hours.name]

    initial = runner.invoke(
        app,
        [
            "meld",
            incoming.name,
            "--left-descendants",
            "--into",
            baseline.name,
            "--right-descendants",
        ],
    )

    assert initial.exit_code == 0, initial.output
    assert "MELD READY · DIRECTIONAL" in initial.output
    assert [
        item["context_name"] for item in provider.payloads[0]["target"]["contexts"]
    ] == [baseline.name, baseline_access.name, baseline_hours.name]
    session = store.load_meld_session(baseline.uid)
    assert session is not None
    assert session.frames[1].include_descendants is True
    assert {
        proposal.owner_context_name for proposal in session.current_assessment.proposals
    } == {baseline_access.name, baseline_hours.name}
    result_labels = {
        result.label for result in MeldResolutionWorkbenchAdapter(session).view().results
    }
    assert any(baseline_access.name in label for label in result_labels)
    assert any(baseline_hours.name in label for label in result_labels)

    applied = runner.invoke(
        app,
        [
            "meld",
            incoming.name,
            "--left-descendants",
            "--into",
            baseline.name,
            "--right-descendants",
            "--accept",
        ],
    )

    assert applied.exit_code == 0, applied.output
    assert tuple(store.load_direct(baseline.name).iter_items()) == ()
    assert [
        memory.content for memory in store.load_direct(baseline_access.name).iter_items()
    ] == ["Only the vehicle entrance is closed."]
    assert [
        memory.content for memory in store.load_direct(baseline_hours.name).iter_items()
    ] == [
        retained.content,
        "Use the Annex ATM during construction.",
    ]
    assert len(store.list_checkpoints(baseline_access.name)) == 1
    assert len(store.list_checkpoints(baseline_hours.name)) == 1
    applied_session = store.load_meld_session(baseline.uid)
    assert applied_session is not None and applied_session.application is not None
    assert [
        receipt.context_name for receipt in applied_session.application.checkpoints
    ] == [baseline_access.name, baseline_hours.name]

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert store.load_direct(baseline_access.name).memories[edited.uid].content == (
        "The parking area is fully closed."
    )
    assert [
        memory.content for memory in store.load_direct(baseline_hours.name).iter_items()
    ] == [retained.content]
    assert store.load_meld_session(baseline.uid).state == "READY_TO_APPLY"

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert store.load_direct(baseline_access.name).memories[edited.uid].content == (
        "Only the vehicle entrance is closed."
    )
    assert store.load_meld_session(baseline.uid).state == "APPLIED"


def test_directional_accept_recovers_after_receipt_save_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, _, _ = _directional_contexts(store)
    provider = DirectionalProvider()
    _patch_provider(monkeypatch, provider)
    initial = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name],
    )
    assert initial.exit_code == 0, initial.output
    original = MemoryStore.save_meld_session
    fail_once = {"value": True}

    def fail_receipt_once(self, session, **kwargs):
        if session.state == "APPLIED" and fail_once["value"]:
            fail_once["value"] = False
            raise OSError("injected directional receipt write failure")
        return original(self, session, **kwargs)

    monkeypatch.setattr(
        MemoryStore,
        "save_meld_session",
        fail_receipt_once,
    )
    interrupted = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )

    assert interrupted.exit_code == 1
    assert "injected directional receipt write failure" in interrupted.output
    assert len(store.list_checkpoints(baseline.name)) == 1
    persisted = store.load_meld_session(baseline.uid)
    assert persisted is not None
    assert persisted.state == "READY_TO_APPLY"

    recovered = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )

    assert recovered.exit_code == 0, recovered.output
    assert "prior application recovered; no duplicate write" in recovered.output
    assert len(store.list_checkpoints(baseline.name)) == 1
    assert store.load_meld_session(baseline.uid).state == "APPLIED"
    assert len(provider.payloads) == 1


def test_zero_change_directional_meld_checkpoints_and_repeats_provider_free(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, baseline_memory = _zero_change_directional_contexts(store)
    provider = ZeroChangeDirectionalProvider()
    _patch_provider(monkeypatch, provider)
    incoming_before = store._context_file(incoming.name).read_bytes()
    baseline_before = store._context_file(baseline.name).read_bytes()

    initial = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name],
    )
    assert initial.exit_code == 0, initial.output
    assert "MELD READY · DIRECTIONAL" in initial.output

    applied = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )

    assert applied.exit_code == 0, applied.output
    assert "MELD APPLIED · DIRECTIONAL" in applied.output
    assert "EFFECTS · ADD 0 · EDIT 0" in applied.output
    current = store.load_direct(baseline.name)
    assert [(memory.uid, memory.content) for memory in current.iter_items()] == [
        (
            baseline_memory.uid,
            "The Campus Store remains open during construction.",
        )
    ]
    assert store._context_file(incoming.name).read_bytes() == incoming_before
    assert store._context_file(baseline.name).read_bytes() == baseline_before
    checkpoints = store.list_checkpoints(baseline.name)
    assert len(checkpoints) == 1
    assert checkpoints[0]["args"]["meld"]["results"] == []
    session = store.load_meld_session(baseline.uid)
    assert session is not None
    assert session.state == "APPLIED"
    assert session.application.result_memory_uids == ()

    repeated = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )
    assert repeated.exit_code == 0, repeated.output
    assert "prior application recovered; no duplicate write" in repeated.output
    assert len(store.list_checkpoints(baseline.name)) == 1
    assert len(provider.payloads) == 1

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert store.load_meld_session(baseline.uid).state == "READY_TO_APPLY"
    assert [
        memory.content for memory in store.load_direct(baseline.name).memories.values()
    ] == ["The Campus Store remains open during construction."]

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert store.load_meld_session(baseline.uid).state == "APPLIED"


def test_public_meld_apply_replays_the_reviewed_version_without_duplicate_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, _ = _zero_change_directional_contexts(store)
    provider = ZeroChangeDirectionalProvider()
    _patch_provider(monkeypatch, provider)
    initial = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name],
    )
    assert initial.exit_code == 0, initial.output

    client = MemCommitClient(root=store.store_dir)
    reviewed = client.open_meld(baseline.name)

    applied = client.apply_meld(
        baseline.name,
        expected_version=reviewed.version,
    )
    repeated = client.apply_meld(
        baseline.name,
        expected_version=reviewed.version,
    )

    assert applied.recovered is False
    assert repeated.recovered is True
    assert repeated.checkpoint_uid == applied.checkpoint_uid
    assert repeated.session.state == "APPLIED"
    assert len(store.list_checkpoints(baseline.name)) == 1
    assert len(provider.payloads) == 1


def test_zero_change_directional_meld_recovers_checkpoint_after_receipt_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, _ = _zero_change_directional_contexts(store)
    provider = ZeroChangeDirectionalProvider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(
            app,
            ["meld", incoming.name, "--into", baseline.name],
        ).exit_code
        == 0
    )
    original = MemoryStore.save_meld_session
    fail_once = {"value": True}

    def fail_receipt_once(self, session, **kwargs):
        if session.state == "APPLIED" and fail_once["value"]:
            fail_once["value"] = False
            raise OSError("injected zero-change receipt write failure")
        return original(self, session, **kwargs)

    monkeypatch.setattr(
        MemoryStore,
        "save_meld_session",
        fail_receipt_once,
    )
    interrupted = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )
    assert interrupted.exit_code == 1
    assert len(store.list_checkpoints(baseline.name)) == 1

    recovered = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )

    assert recovered.exit_code == 0, recovered.output
    assert "prior application recovered; no duplicate write" in recovered.output
    assert len(store.list_checkpoints(baseline.name)) == 1
    assert store.load_meld_session(baseline.uid).state == "APPLIED"
    assert len(provider.payloads) == 1


def test_meld_positional_grammar_and_explicit_alias_boundaries(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, _, _ = _directional_contexts(store)
    provider = DirectionalProvider()
    _patch_provider(monkeypatch, provider)

    help_result = runner.invoke(app, ["meld", "--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "--into" in help_result.output
    assert "--from" in help_result.output
    assert "--to" in help_result.output
    assert "--memory" in help_result.output
    normalized_help = " ".join(help_result.output.replace("│", " ").split())
    assert "[LEFT] [RIGHT] [RESULT]" in normalized_help
    assert "mem meld INCOMING BASELINE" in normalized_help
    assert "mem meld PEER_A PEER_B RESULT_C" in normalized_help

    missing_peers = runner.invoke(
        app,
        ["meld", "--to", baseline.name],
    )
    assert missing_peers.exit_code == 1
    assert "requires PEER A and PEER B before RESULT C" in missing_peers.output

    too_many = runner.invoke(
        app,
        ["meld", incoming.name, baseline.name, "--into", baseline.name],
    )
    assert too_many.exit_code == 1
    assert "accepts at most one positional INCOMING" in too_many.output

    store.set_current(baseline.name)
    one_operand = runner.invoke(app, ["meld", incoming.name])
    assert one_operand.exit_code == 0, one_operand.output
    assert f"INCOMING {incoming.name} → BASELINE / TARGET {baseline.name}" in (
        one_operand.output
    )
    assert len(provider.payloads) == 1

    two_operands = runner.invoke(app, ["meld", incoming.name, baseline.name])
    assert two_operands.exit_code == 0, two_operands.output
    assert len(provider.payloads) == 1

    same_context = runner.invoke(
        app,
        ["meld", incoming.name, incoming.name],
    )
    assert same_context.exit_code == 1
    assert "both resolved" in same_context.output
    assert "INCOMING" in same_context.output
    assert "BASELINE" in same_context.output


def test_symmetric_meld_third_operand_creates_empty_result_without_switching(
    isolated_store,
):
    store = MemoryStore()
    left, right, current = _task2_contexts(store)
    result_name = "task-2/participant/proposal-workspace"

    result = runner.invoke(
        app,
        ["meld", left.name, right.name, result_name],
    )

    assert result.exit_code == 0, result.output
    created = store.load_direct(result_name)
    assert tuple(created.iter_items()) == ()
    assert store.current_context_name() == current.name
    session = store.load_meld_session(created.uid)
    assert session is not None
    assert session.mode == "SYMMETRIC"
    assert session.target.context_name == result_name
    assert f"{left.name} + {right.name} → {result_name}" in result.output
    checkpoints = store.list_checkpoints(result_name)
    assert len(checkpoints) == 1
    assert checkpoints[0]["command"] == "meld"
    assert checkpoints[0]["args"] == {
        "left": left.name,
        "right": right.name,
        "to": result_name,
    }


def test_symmetric_meld_to_creates_missing_basis_and_result_without_switching(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, _ = _task2_contexts(store, with_comparison=False)
    current = ops.init("task-3/orientation")
    store.create_context(current)
    store.set_current(current.name)
    result_name = "task-2/participant/proposal-workspace2"
    provider = Task2CompareProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            "--left-descendants",
            "--to",
            result_name,
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 1
    assert store.current_context_name() == current.name
    analysis = load_comparison_analysis(left.uid, right.uid)
    assert analysis is not None
    assert analysis.include_descendants == (True, False)
    created = store.load_direct(result_name)
    session = store.load_meld_session(created.uid)
    assert session is not None
    assert session.comparison_seed is not None
    assert session.comparison_seed.analysis.uid == analysis.uid


def test_symmetric_meld_explicit_result_adopts_only_empty_or_exact_session(
    isolated_store,
):
    store = MemoryStore()
    left, right, existing = _task2_contexts(store)

    adopted = runner.invoke(
        app,
        ["meld", left.name, right.name, existing.name],
    )
    assert adopted.exit_code == 0, adopted.output
    session = store.load_meld_session(existing.uid)
    assert session is not None
    assert session.mode == "SYMMETRIC"
    assert session.target.context_name == existing.name

    resumed = runner.invoke(
        app,
        ["meld", left.name, right.name, "--to", existing.name],
    )
    assert resumed.exit_code == 0, resumed.output
    assert store.load_meld_session(existing.uid).uid == session.uid

    populated = ops.init("task-2/participant/populated-result")
    ops.add(populated, "Existing unrelated result content.")
    store.save(populated)
    occupied = runner.invoke(
        app,
        ["meld", left.name, right.name, populated.name],
    )
    assert occupied.exit_code == 1
    assert "Result must remain empty" in occupied.output
    assert store.load_meld_session(populated.uid) is None


def test_symmetric_meld_failed_basis_leaves_new_result_absent(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, _ = _task2_contexts(store, with_comparison=False)

    class FailingCompareProvider:
        def complete(self, *args, **kwargs):
            raise ComparisonProviderError("comparison basis failed")

    monkeypatch.setattr(
        "memcommit.commands.meld.connect_codex_chatgpt_provider",
        lambda: FailingCompareProvider(),
    )
    missing_name = "task-2/participant/missing-compare-result"
    missing_compare = runner.invoke(
        app,
        ["meld", left.name, right.name, "--to", missing_name],
    )
    assert missing_compare.exit_code == 1
    assert "comparison basis failed" in missing_compare.output
    assert not store.context_exists(missing_name)


def test_directional_meld_from_rejects_ambiguous_or_missing_baseline(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, _, _ = _directional_contexts(store)

    class UnexpectedProvider:
        def complete(self, *args, **kwargs):
            raise AssertionError("Invalid meld grammar called the provider.")

    _patch_provider(monkeypatch, UnexpectedProvider())
    store.set_current(baseline.name)

    with_into = runner.invoke(
        app,
        ["meld", "--from", incoming.name, "--into", baseline.name],
    )
    assert with_into.exit_code == 2
    assert "--from and --into" in with_into.output

    with_positional = runner.invoke(
        app,
        ["meld", incoming.name, "--from", incoming.name],
    )
    assert with_positional.exit_code == 2
    assert "cannot be combined with positional Contexts" in with_positional.output

    same_context = runner.invoke(app, ["meld", "--from", "."])
    assert same_context.exit_code == 1
    assert "different INCOMING and BASELINE" in same_context.output

    store._write_state({"current": None})
    missing_baseline = runner.invoke(
        app,
        ["meld", "--from", incoming.name],
    )
    assert missing_baseline.exit_code == 1
    assert "No current BASELINE Context" in missing_baseline.output


def test_defer_all_is_provider_free_and_does_not_mutate_target(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(
            app,
            ["meld", left.name, right.name, target.name],
        ).exit_code
        == 0
    )
    before = store._context_file(target.name).read_bytes()

    deferred = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--defer-all"],
    )

    assert deferred.exit_code == 0
    assert "MELD DEFERRED · SYMMETRIC" in deferred.output
    assert len(provider.payloads) == 0
    assert store._context_file(target.name).read_bytes() == before
    assert store.list_checkpoints(target.name) == []


def test_deferred_session_restart_creates_exact_ordered_compare_basis(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(app, ["meld", left.name, right.name, target.name]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["meld", left.name, right.name, target.name, "--defer-all"],
        ).exit_code
        == 0
    )
    deferred = store.load_meld_session(target.uid)
    assert deferred is not None

    compare_provider = Task2CompareProvider()
    _patch_provider(monkeypatch, compare_provider)
    restarted = runner.invoke(
        app,
        ["meld", right.name, left.name, target.name, "--restart"],
    )

    assert restarted.exit_code == 0, restarted.output
    assert len(compare_provider.payloads) == 1
    reverse = load_comparison_analysis(right.uid, left.uid)
    assert reverse is not None
    replacement = store.load_meld_session(target.uid)
    assert replacement is not None
    assert replacement.uid != deferred.uid
    assert replacement.state == "AWAITING_REPLY"
    assert replacement.comparison_seed is not None
    assert replacement.comparison_seed.analysis.uid == reverse.uid
    assert [frame.context_name for frame in replacement.frames] == [
        right.name,
        left.name,
    ]


def test_symmetric_session_resumes_with_peer_arguments_reversed(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(app, ["meld", left.name, right.name, target.name]).exit_code
        == 0
    )

    resumed = runner.invoke(app, ["meld", right.name, left.name, target.name])

    assert resumed.exit_code == 0, resumed.output
    assert "Resumed without calling the semantic provider" in resumed.output
    assert len(provider.payloads) == 0


def test_revision_flags_require_a_semantic_comment_or_choice(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(app, ["meld", left.name, right.name, target.name]).exit_code
        == 0
    )

    result = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--revision", "correct"],
    )

    assert result.exit_code == 2
    assert "require a comment or choice" in result.output


def test_v3_preserve_all_materializes_provider_free_and_remains_non_applying(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)

    class PreserveProvider(Task2Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            if payload["current_turn"]["turn_id"] is None:
                return super().complete(
                    prompt,
                    operation=operation,
                    output_schema=output_schema,
                )
            self.payloads.append(payload)
            assert payload["current_turn"]["scope"] == "REMAINING"
            left_id = payload["frames"][0]["memories"][0]["memory_id"]
            right_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": (
                        "Both advisor policies are retained as explicit "
                        "source-scoped alternatives."
                    ),
                    "relations": [
                        {
                            "relation_key": "r000001",
                            "left_memory_ids": [left_id],
                            "right_memory_ids": [right_id],
                            "kind": "COMPATIBLE",
                            "status": "RESOLVED",
                            "summary": "Both payment policies are preserved.",
                            "reason": (
                                "The whole-set instruction requests explicit "
                                "preservation rather than a default winner."
                            ),
                        }
                    ],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "left_policy",
                            "disposition": "PRESERVE",
                            "content": (
                                "For the applicable study scope, budget CAD "
                                "20–30 per hour in cash, including travel time."
                            ),
                            "reason": "Preserves the first peer's policy.",
                            "relation_keys": ["r000001"],
                            "source_memory_ids": [left_id],
                            "grounded_turn_ids": [],
                        },
                        {
                            "result_key": "right_policy",
                            "disposition": "PRESERVE",
                            "content": (
                                "For the applicable study scope, compensate "
                                "by e-transfer or equivalent-value gift card."
                            ),
                            "reason": "Preserves the second peer's policy.",
                            "relation_keys": ["r000001"],
                            "source_memory_ids": [right_id],
                            "grounded_turn_ids": [],
                        },
                    ],
                    "ready_to_apply": True,
                }
            )

    provider = PreserveProvider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(
            app,
            ["meld", left.name, right.name, target.name],
        ).exit_code
        == 0
    )
    before = store._context_file(target.name).read_bytes()

    result = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--preserve-all"],
    )

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 0
    assert "MELD READY · SYMMETRIC" in result.output
    assert f"IMPACT · mem impact meld --session {store.load_meld_session(target.uid).uid}" in result.output
    assert store._context_file(target.name).read_bytes() == before


def test_user_comment_can_ground_a_new_result_without_peer_attribution():
    left = ops.init("left/user-add")
    ops.add(left, "Compensate participants in cash.")
    right = ops.init("right/user-add")
    ops.add(right, "Compensate participants by e-transfer.")
    target = ops.init("target/user-add")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    initial_provider = Task2Provider()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, initial_provider),
    )
    issue_uid = session.current_assessment.issues[0].uid
    turn = session.start_turn(
        (
            "Keep both source methods. Add that the payment method does not "
            "need to be finalized at proposal time."
        ),
        scope="ISSUE",
        issue_uids=(issue_uid,),
    )

    class AddProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            left_id = payload["frames"][0]["memories"][0]["memory_id"]
            right_id = payload["frames"][1]["memories"][0]["memory_id"]
            turn_id = payload["current_turn"]["turn_id"]
            return json.dumps(
                {
                    "overview": (
                        "Both source methods and one user-supplied "
                        "proposal-stage rule are retained."
                    ),
                    "relations": [
                        {
                            "relation_key": "r000001",
                            "left_memory_ids": [left_id],
                            "right_memory_ids": [right_id],
                            "kind": "COMPATIBLE",
                            "status": "RESOLVED",
                            "summary": "Both payment methods are allowed.",
                            "reason": "The user asked to retain both.",
                        }
                    ],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "methods",
                            "disposition": "SYNTHESIZE",
                            "content": (
                                "Participant compensation may be paid in cash "
                                "or by e-transfer."
                            ),
                            "reason": "Combines both source-supported methods.",
                            "relation_keys": ["r000001"],
                            "source_memory_ids": [left_id, right_id],
                            "grounded_turn_ids": [turn_id],
                        },
                        {
                            "result_key": "proposal_stage",
                            "disposition": "USER_ADD",
                            "content": (
                                "The payment method does not need to be "
                                "finalized at proposal time."
                            ),
                            "reason": "The user supplied this additional rule.",
                            "relation_keys": [],
                            "source_memory_ids": [],
                            "grounded_turn_ids": [turn_id],
                        },
                    ],
                    "ready_to_apply": True,
                }
            )

    session.record_assessment(turn.uid, assess_meld_turn(session, AddProvider()))

    assert session.state == "READY_TO_APPLY"
    addition = next(
        proposal
        for proposal in session.current_assessment.proposals
        if proposal.disposition == "USER_ADD"
    )
    assert addition.source_members == ()
    assert addition.grounded_by_turn_uids == (turn.uid,)
    tampered = session.to_dict()
    proposals = tampered["turns"][-1]["assessment"]["proposals"]
    user_add = next(item for item in proposals if item["disposition"] == "USER_ADD")
    source_derived = next(
        item for item in proposals if item["disposition"] != "USER_ADD"
    )
    user_add["source_members"] = source_derived["source_members"]
    user_add["relation_uids"] = source_derived["relation_uids"]
    with pytest.raises(MeldError, match="must not claim PEER"):
        MeldSession.from_dict(tampered)


def test_source_change_during_provider_call_is_rejected_before_session_save(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    target_before = store._context_file(target.name).read_bytes()

    class MutatingProvider(Task2Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            changed = store.load_direct(left.name)
            memory = next(iter(changed.iter_items()))
            changed.replace(
                type(memory)(
                    uid=memory.uid,
                    content="Changed while the provider was running.",
                )
            )
            store.save(changed)
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    provider = MutatingProvider()
    _patch_provider(monkeypatch, provider)
    initial = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name],
    )
    assert initial.exit_code == 0, initial.output
    saved_before = store.load_meld_session(target.uid)
    assert saved_before is not None
    saved_before_digest = meld_canonical_digest(saved_before.to_dict())

    result = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            target.name,
            "--issue",
            "1",
            "--choice",
            "1",
            "--comment",
            "Keep all supported payment details.",
        ],
    )

    assert result.exit_code == 1
    assert "changed after this meld was analyzed" in result.output
    persisted = store.load_meld_session(target.uid)
    assert persisted is not None
    assert meld_canonical_digest(persisted.to_dict()) == saved_before_digest
    assert store._context_file(target.name).read_bytes() == target_before
    assert store.list_checkpoints(target.name) == []


def test_source_is_rechecked_under_lock_at_the_target_mutation_boundary(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(app, ["meld", left.name, right.name, target.name]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "meld",
                left.name,
                right.name,
                target.name,
                "--issue",
                "1",
                "--choice",
                "1",
                "--comment",
                "Keep all of these payment options.",
            ],
        ).exit_code
        == 0
    )
    original = MemoryStore.save_meld_target

    def mutate_then_save(self, ctx, checkpoint, **kwargs):
        changed = self.load_direct(left.name)
        memory = next(iter(changed.iter_items()))
        changed.replace(
            type(memory)(
                uid=memory.uid,
                content="Changed at the final apply boundary.",
            )
        )
        self.save(changed)
        return original(self, ctx, checkpoint, **kwargs)

    monkeypatch.setattr(MemoryStore, "save_meld_target", mutate_then_save)
    applied = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--accept"],
    )

    assert applied.exit_code == 1
    assert "changed before the meld target could be saved" in applied.output
    assert tuple(store.load_direct(target.name).iter_items()) == ()
    assert store.list_checkpoints(target.name) == []


def test_accept_recovers_checkpoint_after_receipt_save_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(app, ["meld", left.name, right.name, target.name]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "meld",
                left.name,
                right.name,
                target.name,
                "--issue",
                "1",
                "--choice",
                "1",
                "--comment",
                "Keep all of these payment options.",
            ],
        ).exit_code
        == 0
    )
    original = MemoryStore.save_meld_session
    fail_once = {"value": True}

    def fail_receipt_once(self, session, **kwargs):
        if session.state == "APPLIED" and fail_once["value"]:
            fail_once["value"] = False
            raise OSError("injected receipt write failure")
        return original(self, session, **kwargs)

    monkeypatch.setattr(
        MemoryStore,
        "save_meld_session",
        fail_receipt_once,
    )
    interrupted = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--accept"],
    )
    assert interrupted.exit_code == 1
    assert len(store.list_checkpoints(target.name)) == 1
    assert len(tuple(store.load_direct(target.name).iter_items())) == 2
    persisted = store.load_meld_session(target.uid)
    assert persisted is not None
    assert persisted.state == "READY_TO_APPLY"

    recovered = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--accept"],
    )

    assert recovered.exit_code == 0, recovered.output
    assert "prior application recovered; no duplicate write" in recovered.output
    assert len(store.list_checkpoints(target.name)) == 1
    assert store.load_meld_session(target.uid).state == "APPLIED"


def test_applied_accept_rejects_a_target_that_no_longer_matches_receipt(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert (
        runner.invoke(app, ["meld", left.name, right.name, target.name]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "meld",
                left.name,
                right.name,
                target.name,
                "--issue",
                "1",
                "--choice",
                "1",
                "--comment",
                "Keep all of these payment options.",
            ],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["meld", left.name, right.name, target.name, "--accept"],
        ).exit_code
        == 0
    )
    changed = store.load_direct(target.name)
    memory = next(iter(changed.iter_items()))
    changed.replace(
        type(memory)(
            uid=memory.uid,
            content="Tampered after meld application.",
        )
    )
    store.save(changed)

    repeated = runner.invoke(
        app,
        ["meld", left.name, right.name, target.name, "--accept"],
    )

    assert repeated.exit_code == 1
    assert "receipt no longer matches" in repeated.output


def test_meld_rejects_refs_without_dereferencing_them(isolated_store):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    left.add(
        MemoryRef(
            uid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            target_context_uid=right.uid,
            target_context_name=right.name,
            target_memory_uid=next(iter(right.memories)),
        )
    )
    store.save(left)

    with pytest.raises(MeldError, match="direct owned Memories only"):
        MeldSession.create_symmetric(left, right, target)


def test_context_rename_keeps_an_unapplied_meld_target_and_session_bound(
    isolated_store,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    store.save_meld_session(session)

    plan = store.plan_context_rename(target.name, "task-2/relocated-result")
    result = store.rename_contexts(plan)

    relocated = store.load_meld_session(target.uid)
    assert relocated is not None
    assert relocated.target.context_name == "task-2/relocated-result"
    assert store.load_direct("task-2/relocated-result").uid == target.uid
    assert result.meld_session_count == 1


def test_context_rename_rebinds_an_unapplied_meld_compare_seed(isolated_store):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(comparison, target)
    store.save_meld_session(session)

    store.rename_contexts(store.plan_context_rename(left.name, "task-2/renamed-left"))

    rebound = store.load_meld_session(target.uid)
    assert rebound is not None and rebound.comparison_seed is not None
    assert rebound.frames[0].context_name == "task-2/renamed-left"
    assert (
        rebound.comparison_seed.analysis.frames[0].context_name == "task-2/renamed-left"
    )


def test_symmetric_workbench_can_relocate_its_empty_result_before_apply(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    store.save_meld_session(session)
    actions = iter(
        (
            MeldShellAction(
                kind="CHANGE_DESTINATION",
                destination="task-2/reviewed-result",
            ),
            None,
        )
    )
    monkeypatch.setattr(
        meld_command, "run_meld_shell", lambda *args, **kwargs: next(actions)
    )

    relocated = meld_command._run_interactive(
        store=store,
        session=session,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("provider called")
        ),
    )

    assert relocated.target.context_name == "task-2/reviewed-result"
    assert not store.context_exists(target.name)
    assert store.load_direct("task-2/reviewed-result").uid == target.uid


def test_meld_session_save_uses_optimistic_concurrency(isolated_store):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    store.save_meld_session(session)
    stale_digest = meld_canonical_digest(session.to_dict())

    first = store.load_meld_session(target.uid)
    second = store.load_meld_session(target.uid)
    assert first is not None and second is not None
    first.keep_review_only()
    store.save_meld_session(
        first,
        expected_session_digest=stale_digest,
    )
    second.keep_review_only()
    with pytest.raises(
        ConcurrentContextUpdateError,
        match="changed",
    ):
        store.save_meld_session(
            second,
            expected_session_digest=stale_digest,
        )


def test_deleting_target_removes_its_meld_dialogue(isolated_store):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    store.save_meld_session(session)
    path = store._meld_session_path(target.uid)
    assert path.exists()

    store.delete(target.name)

    assert not path.exists()


def test_provider_rejects_incomplete_primary_source_coverage():
    left = ops.init("left")
    ops.add(left, "Left one.")
    ops.add(left, "Left two.")
    right = ops.init("right")
    ops.add(right, "Right one.")
    target = ops.init("target")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()

    class Incomplete:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            left_id = payload["frames"][0]["memories"][0]["memory_id"]
            right_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "Incomplete coverage.",
                    "relations": [
                        {
                            "relation_key": "r",
                            "left_memory_ids": [left_id],
                            "right_memory_ids": [right_id],
                            "kind": "COMPATIBLE",
                            "status": "RESOLVED",
                            "summary": "Only two sources were covered.",
                            "reason": "The second left source was omitted.",
                        }
                    ],
                    "issues": [],
                    "results": [],
                    "ready_to_apply": False,
                }
            )

    with pytest.raises(MeldError, match="cover every source Memory"):
        assess_meld_turn(session, Incomplete())


@pytest.mark.parametrize("mode", ["SYMMETRIC", "DIRECTIONAL"])
def test_meld_output_schema_uses_the_codex_supported_subset(mode):
    source_ids = tuple(f"m{index:06d}" for index in range(1, 5))
    schema = meld_output_schema(
        source_ids,
        mode=mode,
        target_context_count=2 if mode == "DIRECTIONAL" else 1,
    )
    allowed_keywords = {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "description",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    }

    def assert_supported(node):
        assert set(node) <= allowed_keywords
        properties = node.get("properties", {})
        assert isinstance(properties, dict)
        for child in properties.values():
            assert_supported(child)
        items = node.get("items")
        if items is not None:
            assert_supported(items)

    assert_supported(schema)
    paired = schema["properties"]["paired_relations"]["items"]
    assert "left_memory_ids" not in paired["properties"]
    assert "right_memory_ids" not in paired["properties"]
    assert "DISTINCT" not in paired["properties"]["kind"]["enum"]
    distinct = schema["properties"]["distinct_relations"]["items"]
    assert "memory_ids" not in distinct["properties"]
    assert distinct["properties"]["kind"]["enum"] == ["DISTINCT"]
    assignments = schema["properties"]["source_assignments"]
    assert assignments["minItems"] == len(source_ids)
    assert assignments["maxItems"] == len(source_ids)
    assert assignments["items"]["properties"]["source_memory_id"]["enum"] == list(
        source_ids
    )
    if mode == "DIRECTIONAL":
        result = schema["properties"]["results"]["items"]
        assert "target_context_id" in result["required"]


def test_source_indexed_meld_assignments_reconstruct_complete_relations():
    left = ops.init("left/source-indexed")
    left_memory = ops.add(left, "Left policy.")
    right = ops.init("right/source-indexed")
    right_memory = ops.add(right, "Right policy.")
    target = ops.init("target/source-indexed")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()

    class SourceIndexed:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            left_id = payload["frames"][0]["memories"][0]["memory_id"]
            right_id = payload["frames"][1]["memories"][0]["memory_id"]
            assert output_schema["properties"]["source_assignments"][
                "minItems"
            ] == 2
            return json.dumps(
                {
                    "overview": "The two source policies are equivalent.",
                    "paired_relations": [
                        {
                            "relation_key": "shared",
                            "kind": "EQUIVALENT",
                            "status": "RESOLVED",
                            "summary": "Both sources state one policy.",
                            "reason": "Their operational meaning agrees.",
                        }
                    ],
                    "distinct_relations": [],
                    "source_assignments": [
                        {
                            "source_memory_id": right_id,
                            "relation_key": "shared",
                        },
                        {
                            "source_memory_id": left_id,
                            "relation_key": "shared",
                        },
                    ],
                    "issues": [],
                    "results": [],
                    "ready_to_apply": False,
                }
            )

    assessment = assess_meld_turn(session, SourceIndexed())

    assert len(assessment.relations) == 1
    assert [member.memory_uid for member in assessment.relations[0].members] == [
        left_memory.uid,
        right_memory.uid,
    ]


def test_source_indexed_meld_assignments_reject_duplicate_source_alias():
    left = ops.init("left/source-indexed-duplicate")
    ops.add(left, "Left policy.")
    right = ops.init("right/source-indexed-duplicate")
    ops.add(right, "Right policy.")
    target = ops.init("target/source-indexed-duplicate")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()

    class DuplicateSourceIndexed:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            left_id = payload["frames"][0]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "Invalid duplicate assignment.",
                    "paired_relations": [
                        {
                            "relation_key": "shared",
                            "kind": "EQUIVALENT",
                            "status": "RESOLVED",
                            "summary": "Both sources state one policy.",
                            "reason": "Their operational meaning agrees.",
                        }
                    ],
                    "distinct_relations": [],
                    "source_assignments": [
                        {
                            "source_memory_id": left_id,
                            "relation_key": "shared",
                        },
                        {
                            "source_memory_id": left_id,
                            "relation_key": "shared",
                        },
                    ],
                    "issues": [],
                    "results": [],
                    "ready_to_apply": False,
                }
            )

    with pytest.raises(MeldError, match="cover every source Memory exactly once"):
        assess_meld_turn(session, DuplicateSourceIndexed())


def test_provider_parser_rejects_duplicate_aliases_without_unique_items():
    left = ops.init("left/duplicate-alias")
    ops.add(left, "Left policy.")
    right = ops.init("right/duplicate-alias")
    ops.add(right, "Right policy.")
    target = ops.init("target/duplicate-alias")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()

    class DuplicateAlias(Task2Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            value = json.loads(
                super().complete(
                    prompt,
                    operation=operation,
                    output_schema=output_schema,
                )
            )
            left_ids = value["relations"][0]["left_memory_ids"]
            left_ids.append(left_ids[0])
            return json.dumps(value)

    with pytest.raises(MeldError, match="duplicate left Memory ids"):
        assess_meld_turn(session, DuplicateAlias())


def test_directional_edit_target_field_supplies_baseline_provenance():
    incoming = ops.init("incoming/target-field")
    incoming_memory = ops.add(
        incoming,
        "Only the vehicle entrance is closed.",
    )
    baseline = ops.init("baseline/target-field")
    baseline_memory = ops.add(
        baseline,
        "The parking area is fully closed.",
    )
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()

    class TargetFieldOnly:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            incoming_id = payload["frames"][0]["memories"][0]["memory_id"]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": ("The incoming rule narrows one baseline closure."),
                    "relations": [
                        {
                            "relation_key": "parking",
                            "left_memory_ids": [incoming_id],
                            "right_memory_ids": [baseline_id],
                            "kind": "CONFLICT",
                            "status": "RESOLVED",
                            "summary": "The closure scopes differ.",
                            "reason": "Incoming evidence is more specific.",
                        }
                    ],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "parking_edit",
                            "operation": "EDIT",
                            "target_memory_ids": [baseline_id],
                            "disposition": "SYNTHESIZE",
                            "content": "Only the vehicle entrance is closed.",
                            "reason": "Applies the supported narrower scope.",
                            "relation_keys": ["parking"],
                            # The target has its own dedicated citation field.
                            "source_memory_ids": [incoming_id],
                            "grounded_turn_ids": [],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    assessment = assess_meld_turn(session, TargetFieldOnly())

    proposal = assessment.proposals[0]
    assert proposal.memory_uid == baseline_memory.uid
    assert {member.memory_uid for member in proposal.source_members} == {
        incoming_memory.uid,
        baseline_memory.uid,
    }


def test_directional_v6_rejects_ungrounded_topical_synthesis():
    incoming = ops.init("incoming/preservation-v6")
    first = ops.add(incoming, "Use the east entrance on Monday.")
    second = ops.add(incoming, "Use the west entrance on Tuesday.")
    baseline = ops.init("baseline/preservation-v6")
    ops.add(baseline, "Construction changes building access by day.")
    session = MeldSession.create_directional(incoming, baseline)
    assert session.schema_version == MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION
    session.start_initial_analysis()

    class TopicalSummary:
        def complete(self, prompt, *, operation, output_schema=None):
            assert "relation groups are analysis units" in prompt
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            incoming_ids = [
                memory["memory_id"] for memory in payload["frames"][0]["memories"]
            ]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "Both daily access facts are summarized together.",
                    "paired_relations": [
                        {
                            "relation_key": "access",
                            "left_memory_ids": incoming_ids,
                            "right_memory_ids": [baseline_id],
                            "kind": "SCOPED",
                            "status": "RESOLVED",
                            "summary": "The facts have different daily scopes.",
                            "reason": "They concern the same construction topic.",
                        }
                    ],
                    "distinct_relations": [],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "access_summary",
                            "operation": "ADD",
                            "target_memory_ids": [],
                            "disposition": "SYNTHESIZE",
                            "content": "Use different entrances on Monday and Tuesday.",
                            "reason": "Summarizes both access facts.",
                            "relation_keys": ["access"],
                            "source_memory_ids": incoming_ids,
                            "grounded_turn_ids": [],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    assessment = assess_meld_turn(session, TopicalSummary())
    with pytest.raises(MeldError, match="explicit user-grounded"):
        session.record_assessment(session.current_turn.uid, assessment)
    assert {memory.uid for memory in incoming.memories.values()} == {
        first.uid,
        second.uid,
    }


def test_directional_v6_accepts_one_exact_preserve_add_per_incoming_memory():
    incoming = ops.init("incoming/preservation-v6-exact")
    contents = (
        "Use the east entrance on Monday.",
        "Use the west entrance on Tuesday.",
    )
    for content in contents:
        ops.add(incoming, content)
    baseline = ops.init("baseline/preservation-v6-exact")
    ops.add(baseline, "Construction changes building access by day.")
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()

    class ExactPreserves:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            incoming_records = payload["frames"][0]["memories"]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "Both scoped access facts remain independently editable.",
                    "paired_relations": [
                        {
                            "relation_key": "access",
                            "left_memory_ids": [
                                memory["memory_id"] for memory in incoming_records
                            ],
                            "right_memory_ids": [baseline_id],
                            "kind": "SCOPED",
                            "status": "RESOLVED",
                            "summary": "The facts have different daily scopes.",
                            "reason": "Each day remains an independent instruction.",
                        }
                    ],
                    "distinct_relations": [],
                    "issues": [],
                    "results": [
                        {
                            "result_key": f"access_{index}",
                            "operation": "ADD",
                            "target_memory_ids": [],
                            "disposition": "PRESERVE",
                            "content": memory["content"],
                            "reason": "Preserves one independently revisable fact.",
                            "relation_keys": ["access"],
                            "source_memory_ids": [memory["memory_id"]],
                            "grounded_turn_ids": [],
                        }
                        for index, memory in enumerate(incoming_records, start=1)
                    ],
                    "ready_to_apply": True,
                }
            )

    assessment = assess_meld_turn(session, ExactPreserves())
    session.record_assessment(session.current_turn.uid, assessment)

    assert [proposal.content for proposal in session.current_assessment.proposals] == list(
        contents
    )
    assert all(
        proposal.disposition == "PRESERVE"
        and len(proposal.source_members) == 1
        for proposal in session.current_assessment.proposals
    )


def test_directional_validation_repairs_one_rejected_assessment_before_save(
    isolated_store,
):
    store = MemoryStore()
    incoming = ops.init("incoming/preservation-repair")
    incoming_memory = ops.add(incoming, "Use the east entrance on Monday.")
    baseline = ops.init("baseline/preservation-repair")
    ops.add(baseline, "Construction changes building access by day.")
    store.save(incoming)
    store.save(baseline)
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()

    class RepairingProvider:
        def __init__(self):
            self.operations = []

        def complete(self, prompt, *, operation, output_schema=None):
            self.operations.append(operation)
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            if operation == "meld_contexts_repair":
                assert "validation_error" in payload
                assert "exact content" in payload["validation_error"]
                repaired = payload["rejected_assessment"]
                repaired["results"][0]["content"] = payload["frames"][0][
                    "memories"
                ][0]["content"]
                return json.dumps(repaired)
            incoming_id = payload["frames"][0]["memories"][0]["memory_id"]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "The incoming access fact remains independently editable.",
                    "paired_relations": [
                        {
                            "relation_key": "access",
                            "left_memory_ids": [incoming_id],
                            "right_memory_ids": [baseline_id],
                            "kind": "SCOPED",
                            "status": "RESOLVED",
                            "summary": "The incoming fact supplies a dated access scope.",
                            "reason": "Its exact day remains operationally relevant.",
                        }
                    ],
                    "distinct_relations": [],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "access_add",
                            "operation": "ADD",
                            "target_memory_ids": [],
                            "disposition": "PRESERVE",
                            # This paraphrase passes the output schema and decoder
                            # but fails the session's exact-preservation contract.
                            "content": "Use the eastern entrance on Monday.",
                            "reason": "Preserves the dated access fact.",
                            "relation_keys": ["access"],
                            "source_memory_ids": [incoming_id],
                            "grounded_turn_ids": [],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    provider = RepairingProvider()
    repaired = meld_command._assess_and_save(
        store=store,
        session=session,
        provider_factory=lambda: provider,
        expected_session_digest=None,
    )

    assert provider.operations == ["meld_contexts", "meld_contexts_repair"]
    assert repaired.current_assessment is not None
    assert repaired.current_assessment.proposals[0].content == incoming_memory.content
    saved = store.load_meld_session(baseline.uid)
    assert saved is not None
    assert saved.current_assessment is not None
    assert saved.current_assessment.proposals[0].content == incoming_memory.content
    assert store.load_direct(baseline.name).to_dict() == baseline.to_dict()


def test_followup_meld_turn_uses_shared_interactive_wait(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left = ops.init("left/followup-wait")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("right/followup-wait")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("target/followup-wait")
    for context in (left, right, target):
        store.save(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(comparison, target)
    store.save_meld_session(session, expected_session_digest=None)
    expected = meld_canonical_digest(session.to_dict())
    issue_uid = session.current_assessment.issues[0].uid
    session.start_turn(
        "Keep all supported compensation details.",
        scope="ISSUE",
        issue_uids=(issue_uid,),
    )

    calls = []

    class Progress:
        def update(self, stage, *, step):
            calls.append(("UPDATE", stage, step))

    def run_wait(operation, stage, *, total, work, return_view, context_view):
        return_text = "".join(fragment[1] for fragment in return_view.text)
        assert return_view.title == "PREVIOUS MELD REPORT"
        assert "PENDING TURN · SUBMITTED" in return_text
        assert "Keep all supported compensation details." in return_text
        assert context_view.title == "MELD INPUTS"
        assert "Keep all supported compensation details." in context_view.text
        calls.append(("WAIT", operation, stage, total))
        return work(Progress())

    monkeypatch.setattr(meld_command, "run_command_wait", run_wait)

    revised = meld_command._assess_and_save(
        store=store,
        session=session,
        provider_factory=Task2Provider,
        expected_session_digest=expected,
    )

    assert calls == [
        ("WAIT", "MELD", "connecting provider", 2),
        ("UPDATE", "analyzing meld turn", 2),
    ]
    assert len(revised.turns) == 2
    assert revised.current_assessment is not None
    saved = store.load_meld_session(target.uid)
    assert saved is not None
    assert saved.current_turn.uid == revised.current_turn.uid
    assert saved.current_assessment is not None


def test_followup_meld_turn_reuses_exact_saved_resolution_branch_without_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    scope = "ALL"
    left = ops.init("left/branch-cache-all")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("right/branch-cache-all")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("target/branch-cache-all")
    for context in (left, right, target):
        store.save(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    base = MeldSession.create_symmetric_from_comparison(comparison, target)
    base.start_turn(
        "Keep all supported compensation details.",
        scope=scope,
    )
    store.save_meld_session(base, expected_session_digest=None)
    base_digest = meld_canonical_digest(base.to_dict())

    provider = Task2Provider()
    first = meld_command._assess_and_save(
        store=store,
        session=base,
        provider_factory=lambda: provider,
        expected_session_digest=base_digest,
    )
    assert len(provider.payloads) == 1
    branch_files = list(store.meld_resolution_branches_dir.glob("*.json"))
    assert len(branch_files) == 1
    branch = store.load_meld_resolution_branch(branch_files[0].stem)
    assert branch is not None
    assert branch.branch_kind == "WHOLE_SET_STRATEGY"
    assert branch.scope == scope
    assert branch.instruction == "Keep all supported compensation details."

    # Recreate the exact frozen semantic base with new session and turn UUIDs.
    # Study runs may regenerate those graph identities even when the reviewed
    # strategy, source evidence, and target contract are unchanged.
    pending = MeldSession.create_symmetric_from_comparison(comparison, target)
    pending.start_turn(
        "Keep all supported compensation details.",
        scope=scope,
    )
    assert pending.uid != first.uid
    assert pending.current_turn.uid != first.current_turn.uid
    first_digest = meld_canonical_digest(first.to_dict())
    store.save_meld_session(
        pending,
        expected_session_digest=first_digest,
    )
    restored_digest = meld_canonical_digest(pending.to_dict())
    monkeypatch.setattr(
        meld_command,
        "run_command_wait",
        lambda *args, **kwargs: pytest.fail(
            "an exact saved Meld branch must not open a provider wait"
        ),
    )

    reused = meld_command._assess_and_save(
        store=store,
        session=pending,
        provider_factory=lambda: pytest.fail(
            "an exact saved Meld branch must not connect a provider"
        ),
        expected_session_digest=restored_digest,
    )

    assert reused.current_assessment is not None
    assert [
        proposal.content for proposal in reused.current_assessment.proposals
    ] == [proposal.content for proposal in first.current_assessment.proposals]
    assert reused.current_assessment.ready_to_apply
    assert reused.uid == pending.uid
    assert len(list(store.meld_resolution_branches_dir.glob("*.json"))) == 1
    raw_branch = json.loads(branch_files[0].read_text(encoding="utf-8"))
    raw_branch["completion_sha256"] = "0" * 64
    branch_files[0].write_text(json.dumps(raw_branch), encoding="utf-8")
    with pytest.raises(ValueError, match="Saved Meld resolution branch is invalid"):
        store.load_meld_resolution_branch(branch_files[0].stem)


def test_meld_choice_branches_persist_only_the_selected_local_option(
    isolated_store,
):
    store = MemoryStore()
    left = ops.init("left/local-choice")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("right/local-choice")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("target/local-choice")
    for context in (left, right, target):
        store.save(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(comparison, target)
    store.save_meld_session(session, expected_session_digest=None)
    issue = session.current_assessment.issues[0]
    option = issue.options[1]

    branches = MeldChoiceBranchSet.empty(session).with_response(
        session,
        issue_uid=issue.uid,
        option_uid=option.uid,
        explanation="Use this scope for the study condition.",
    )
    store.save_meld_choice_branches(session, branches)

    restored = store.load_meld_choice_branches(session)
    assert restored.response_for(issue.uid) == (
        option.uid,
        "Use this scope for the study condition.",
    )
    record = json.loads(
        next(store.meld_choice_branches_dir.glob("*.json")).read_text(
            encoding="utf-8"
        )
    )
    assert set(record["branches"][0]) == {
        "issue_uid",
        "option_uid",
        "explanation",
    }
    assert "completion" not in json.dumps(record)
    assert "proposal" not in json.dumps(record)


def test_meld_workbench_restores_local_choice_without_calling_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left = ops.init("left/reopen-choice")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("right/reopen-choice")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("target/reopen-choice")
    for context in (left, right, target):
        store.save(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(comparison, target)
    store.save_meld_session(session, expected_session_digest=None)
    issue = session.current_assessment.issues[0]
    option = issue.options[0]

    def select_and_close(current, **kwargs):
        assert current.uid == session.uid
        kwargs["draft_saver"](issue.uid, option.uid, "Prefer this condition.")
        return None

    monkeypatch.setattr(meld_command, "run_meld_shell", select_and_close)
    meld_command._run_interactive(
        store=store,
        session=session,
        provider_factory=lambda: pytest.fail("local choices need no provider"),
    )

    def verify_and_close(current, **kwargs):
        assert current.uid == session.uid
        assert kwargs["draft_loader"](issue.uid) == (
            option.uid,
            "Prefer this condition.",
        )
        return None

    monkeypatch.setattr(meld_command, "run_meld_shell", verify_and_close)
    meld_command._run_interactive(
        store=store,
        session=session,
        provider_factory=lambda: pytest.fail("restoring choices needs no provider"),
    )


def test_completed_meld_reconciliation_does_not_reapply_stale_local_choices(
    isolated_store,
):
    store = MemoryStore()
    left = ops.init("left/stale-choice")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("right/stale-choice")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("target/stale-choice")
    for context in (left, right, target):
        store.save(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(comparison, target)
    store.save_meld_session(session, expected_session_digest=None)
    initial_digest = meld_canonical_digest(session.to_dict())
    issue = session.current_assessment.issues[0]
    branches = MeldChoiceBranchSet.empty(session).with_response(
        session,
        issue_uid=issue.uid,
        option_uid=issue.options[0].uid,
        explanation="",
    )
    store.save_meld_choice_branches(session, branches)
    session.start_turn(
        "Keep all supported compensation details.",
        scope="ALL",
    )
    store.save_meld_session(
        session,
        expected_session_digest=initial_digest,
    )

    revised = meld_command._assess_and_save(
        store=store,
        session=session,
        provider_factory=Task2Provider,
        expected_session_digest=meld_canonical_digest(session.to_dict()),
    )

    assert store.load_meld_choice_branches(revised).branches == ()


def test_issue_scoped_meld_turn_does_not_publish_a_semantic_outcome_branch(
    isolated_store,
):
    store = MemoryStore()
    left = ops.init("left/no-issue-outcome")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("right/no-issue-outcome")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("target/no-issue-outcome")
    for context in (left, right, target):
        store.save(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(comparison, target)
    issue = session.current_assessment.issues[0]
    session.start_turn(
        "Keep all supported compensation details.",
        scope="ISSUE",
        issue_uids=(issue.uid,),
    )
    store.save_meld_session(session, expected_session_digest=None)

    meld_command._assess_and_save(
        store=store,
        session=session,
        provider_factory=Task2Provider,
        expected_session_digest=meld_canonical_digest(session.to_dict()),
    )

    assert not list(store.meld_resolution_branches_dir.glob("*.json"))


def test_declared_study_meld_branch_is_available_in_a_fresh_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")
    Config().update(
        {
            "semantic_provider": "codex_chatgpt",
            "codex_chatgpt_model": "gpt-5.6-sol",
            "codex_chatgpt_reasoning_effort": "medium",
        }
    )
    store = MemoryStore()
    description = ops.init("task-2/description")
    ops.add(description, "Combine both advisors' supported proposal guidance.")
    left = ops.init("task-2/advisor1")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("task-2/advisor2")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("task-2/participant/proposal-workspace")
    for context in (description, left, right, target):
        store.save(context)
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    prepared = MeldSession.create_symmetric_from_comparison(comparison, target)
    prepared.start_turn(
        "Keep all supported compensation details.",
        scope="ALL",
    )
    store.save_meld_session(prepared, expected_session_digest=None)
    prepared_digest = meld_canonical_digest(prepared.to_dict())
    assessed = meld_command._assess_and_save(
        store=store,
        session=prepared,
        provider_factory=Task2Provider,
        expected_session_digest=prepared_digest,
    )
    branch_path = next(store.meld_resolution_branches_dir.glob("*.json"))
    branch = store.load_meld_resolution_branch(branch_path.stem)
    assert branch is not None

    baseline_uid = str(uuid.uuid4())
    profile = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="fresh-study-profile",
        kind="MANAGED",
        source={
            "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
            "study_uid": str(uuid.uuid4()),
            "study_name": "fresh-study-profile",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": baseline_uid,
            "baseline_profile_name": "study-baseline",
        },
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=profile.uid,
        profiles=(profile,),
    )
    configured = branch.configured_provider
    key, artifact = build_meld_resolution_prewarm_artifact(
        task="task-2",
        task_description=description,
        prepared_branches=((assessed, branch),),
        provider=configured["provider"],
        model=configured["model"],
        reasoning=configured["reasoning_effort"],
        offline_provider_seconds=3.0,
    )
    publish_artifact(
        store.store_dir,
        baseline_profile_uid=baseline_uid,
        operation="MELD_RESOLUTION",
        task="task-2",
        key=key,
        artifact=artifact,
    )
    installed = install_declared_meld_resolution_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    assert installed.declared == installed.installed == 1
    assert installed.branch_count == 1
    Config().update({"codex_chatgpt_reasoning_effort": "none"})

    # A new Study run has different Meld graph identities and no ad-hoc cache.
    branch_path.unlink()
    pending = MeldSession.create_symmetric_from_comparison(comparison, target)
    pending.start_turn(
        "Keep all supported compensation details.",
        scope="ALL",
    )
    store.save_meld_session(
        pending,
        expected_session_digest=meld_canonical_digest(assessed.to_dict()),
    )
    pending_digest = meld_canonical_digest(pending.to_dict())
    monkeypatch.setattr(
        meld_command,
        "run_command_wait",
        lambda *args, **kwargs: pytest.fail(
            "an installed Study Meld branch must not open a provider wait"
        ),
    )

    restored = meld_command._assess_and_save(
        store=store,
        session=pending,
        provider_factory=lambda: pytest.fail(
            "an installed Study Meld branch must not connect a provider"
        ),
        expected_session_digest=pending_digest,
    )

    assert restored.current_assessment is not None
    assert restored.current_assessment.ready_to_apply
    assert [
        proposal.content for proposal in restored.current_assessment.proposals
    ] == [proposal.content for proposal in assessed.current_assessment.proposals]
    assert store.load_meld_resolution_branch(branch.key) is not None


def test_each_meld_option_has_a_distinct_exact_request_digest():
    left = ops.init("left/choice-cache-key")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("right/choice-cache-key")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("target/choice-cache-key")
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    keys = []
    for option_index in (0, 1):
        session = MeldSession.create_symmetric_from_comparison(comparison, target)
        issue = session.current_assessment.issues[0]
        session.start_turn(
            f"Choose this reading: {issue.options[option_index].text}",
            scope="ISSUE",
            issue_uids=(issue.uid,),
        )
        keys.append(meld_turn_request_digest(session))

    assert keys[0] != keys[1]


def test_initial_meld_has_no_review_report_to_restore():
    incoming = ops.init("wait/incoming")
    baseline = ops.init("wait/baseline")
    ops.add(incoming, "Incoming fact.")
    ops.add(baseline, "Baseline fact.")
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()

    with pytest.raises(ValueError, match="requires a submitted turn"):
        meld_command._meld_wait_view(session)


def test_meld_wait_view_styles_memory_objects_without_tinting_report_prose():
    fragments = meld_command._meld_wait_fragments(
        "WHAT MEM UNDERSTOOD\nNeutral report prose.\n"
        "PROPOSED TARGET MEMORIES\n"
        "  +  1. [PRESERVE] One proposed Memory.\n"
        "       WHY · Supporting explanation."
    )

    assert ("class:section", "WHAT MEM UNDERSTOOD\n") in fragments
    assert (
        "class:memory-object",
        "  +  1. [PRESERVE] One proposed Memory.\n",
    ) in fragments
    assert ("", "Neutral report prose.\n") in fragments
    assert ("", "       WHY · Supporting explanation.") in fragments


def test_directional_validation_repair_is_bounded_and_publishes_nothing(
    isolated_store,
):
    store = MemoryStore()
    incoming = ops.init("incoming/preservation-repair-fails")
    ops.add(incoming, "Use the east entrance on Monday.")
    baseline = ops.init("baseline/preservation-repair-fails")
    ops.add(baseline, "Construction changes building access by day.")
    store.save(incoming)
    store.save(baseline)
    original_baseline = baseline.to_dict()
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()

    class InvalidTwice:
        def __init__(self):
            self.operations = []
            self.first_response = None

        def complete(self, prompt, *, operation, output_schema=None):
            self.operations.append(operation)
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            if operation == "meld_contexts_repair":
                return json.dumps(payload["rejected_assessment"])
            incoming_id = payload["frames"][0]["memories"][0]["memory_id"]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "The incoming access fact is paraphrased.",
                    "paired_relations": [
                        {
                            "relation_key": "access",
                            "left_memory_ids": [incoming_id],
                            "right_memory_ids": [baseline_id],
                            "kind": "SCOPED",
                            "status": "RESOLVED",
                            "summary": "The incoming fact has a dated scope.",
                            "reason": "The date remains operationally relevant.",
                        }
                    ],
                    "distinct_relations": [],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "access_add",
                            "operation": "ADD",
                            "target_memory_ids": [],
                            "disposition": "PRESERVE",
                            "content": "Use the eastern entrance on Monday.",
                            "reason": "Paraphrases the dated access fact.",
                            "relation_keys": ["access"],
                            "source_memory_ids": [incoming_id],
                            "grounded_turn_ids": [],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    provider = InvalidTwice()
    with pytest.raises(MeldError, match="validation repair failed"):
        meld_command._assess_and_save(
            store=store,
            session=session,
            provider_factory=lambda: provider,
            expected_session_digest=None,
        )

    assert provider.operations == ["meld_contexts", "meld_contexts_repair"]
    assert store.load_meld_session(baseline.uid) is None
    assert store.load_direct(baseline.name).to_dict() == original_baseline


def test_directional_schema_five_keeps_legacy_materialization_readable():
    incoming = ops.init("incoming/preservation-v5")
    ops.add(incoming, "Use the east entrance on Monday.")
    ops.add(incoming, "Use the west entrance on Tuesday.")
    baseline = ops.init("baseline/preservation-v5")
    ops.add(baseline, "Construction changes building access by day.")
    value = MeldSession.create_directional(incoming, baseline).to_dict()
    value["schema_version"] = 5
    session = MeldSession.from_dict(value)
    session.start_initial_analysis()

    class LegacyTopicalSummary:
        def complete(self, prompt, *, operation, output_schema=None):
            assert "relation groups are analysis units" not in prompt
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            incoming_ids = [
                memory["memory_id"] for memory in payload["frames"][0]["memories"]
            ]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "Legacy materialization remains resumable.",
                    "paired_relations": [
                        {
                            "relation_key": "access",
                            "left_memory_ids": incoming_ids,
                            "right_memory_ids": [baseline_id],
                            "kind": "SCOPED",
                            "status": "RESOLVED",
                            "summary": "The facts have daily scopes.",
                            "reason": "They concern the same topic.",
                        }
                    ],
                    "distinct_relations": [],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "access_summary",
                            "operation": "ADD",
                            "target_memory_ids": [],
                            "disposition": "SYNTHESIZE",
                            "content": "Use different entrances on Monday and Tuesday.",
                            "reason": "Legacy broad result.",
                            "relation_keys": ["access"],
                            "source_memory_ids": incoming_ids,
                            "grounded_turn_ids": [],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    assessment = assess_meld_turn(session, LegacyTopicalSummary())
    session.record_assessment(session.current_turn.uid, assessment)
    assert session.state == "READY_TO_APPLY"


def test_directional_edit_target_must_belong_to_baseline():
    incoming = ops.init("incoming/invalid-edit-target")
    ops.add(incoming, "Incoming policy.")
    baseline = ops.init("baseline/invalid-edit-target")
    ops.add(baseline, "Baseline policy.")
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()

    class IncomingTarget:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
            incoming_id = payload["frames"][0]["memories"][0]["memory_id"]
            baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": "The response targets the wrong frame.",
                    "relations": [
                        {
                            "relation_key": "policy",
                            "left_memory_ids": [incoming_id],
                            "right_memory_ids": [baseline_id],
                            "kind": "CONFLICT",
                            "status": "RESOLVED",
                            "summary": "The policies differ.",
                            "reason": "Their instructions are incompatible.",
                        }
                    ],
                    "issues": [],
                    "results": [
                        {
                            "result_key": "invalid_edit",
                            "operation": "EDIT",
                            "target_memory_ids": [incoming_id],
                            "disposition": "SYNTHESIZE",
                            "content": "Invalid replacement.",
                            "reason": "This target is not authoritative.",
                            "relation_keys": ["policy"],
                            "source_memory_ids": [incoming_id],
                            "grounded_turn_ids": [],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    with pytest.raises(MeldError, match="outside the BASELINE"):
        assess_meld_turn(session, IncomingTarget())


def test_provider_parser_enforces_option_limit_without_schema_help():
    left = ops.init("left/options")
    ops.add(left, "Left policy.")
    right = ops.init("right/options")
    ops.add(right, "Right policy.")
    target = ops.init("target/options")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()

    class TooManyOptions(Task2Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            value = json.loads(
                super().complete(
                    prompt,
                    operation=operation,
                    output_schema=output_schema,
                )
            )
            value["issues"][0]["options"] = [
                {"label": f"Option {index}", "text": f"Reading {index}."}
                for index in range(6)
            ]
            return json.dumps(value)

    with pytest.raises(MeldError, match="too many options"):
        assess_meld_turn(session, TooManyOptions())


def test_strict_model_rejects_impossible_state_and_relation_shapes():
    left = ops.init("left/strict")
    ops.add(left, "Left policy.")
    right = ops.init("right/strict")
    ops.add(right, "Right policy.")
    target = ops.init("target/strict")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )

    pending = session.to_dict()
    pending["state"] = "PENDING_ANALYSIS"
    with pytest.raises(MeldError, match="cannot remain PENDING"):
        MeldSession.from_dict(pending)

    duplicate_source = session.to_dict()
    duplicate_source["frames"][1]["context_uid"] = duplicate_source["frames"][0][
        "context_uid"
    ]
    with pytest.raises(MeldError, match="Duplicate meld source"):
        MeldSession.from_dict(duplicate_source)

    cross_peer_distinct = session.to_dict()
    cross_peer_distinct["turns"][0]["assessment"]["relations"][0]["kind"] = "DISTINCT"
    with pytest.raises(MeldError, match="DISTINCT"):
        MeldSession.from_dict(cross_peer_distinct)


def test_user_add_cannot_claim_peer_source_evidence():
    left = ops.init("left/bad-user-add")
    ops.add(left, "Left policy.")
    right = ops.init("right/bad-user-add")
    ops.add(right, "Right policy.")
    target = ops.init("target/bad-user-add")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )
    issue_uid = session.current_assessment.issues[0].uid
    turn = session.start_turn(
        "Keep all supported details.",
        scope="ISSUE",
        issue_uids=(issue_uid,),
    )

    class Misattributed(Task2Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            value = json.loads(
                super().complete(
                    prompt,
                    operation=operation,
                    output_schema=output_schema,
                )
            )
            value["results"][1]["disposition"] = "USER_ADD"
            return json.dumps(value)

    with pytest.raises(MeldError, match="USER_ADD with invalid evidence"):
        assess_meld_turn(session, Misattributed())
    assert turn.assessment is None


def test_meld_shell_selects_one_issue_reading_from_the_compact_surface():
    left = ops.init("left/shell")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/shell")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/shell")
    comparison = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(
        comparison,
        target,
    )

    with create_pipe_input() as pipe_input:
        option_count = len(comparison.issues[0].options)
        pipe_input.send_text("\r" + "\x1b[B" * option_count + "\r")
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is not None
    assert action.kind == "COMMENT_ALL"
    assert "Choose this reading:" in action.comment
    assert comparison.issues[0].options[0].text in action.comment


def test_ready_meld_applies_from_the_compact_apply_row():
    left = ops.init("left/report-apply")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/report-apply")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/report-apply")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    provider = Task2Provider()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, provider),
    )
    issue_uid = session.current_assessment.issues[0].uid
    session.start_turn(
        "Keep all supported details.",
        scope="ISSUE",
        issue_uids=(issue_uid,),
    )
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, provider),
    )
    assert session.state == "READY_TO_APPLY"

    with create_pipe_input() as pipe_input:
        # The separated Apply row is the one confirmation; no exact-command
        # review screen follows it.
        pipe_input.send_text("\r")
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is not None
    assert action.kind == "ACCEPT"


def test_ready_meld_review_report_cannot_accept_or_apply():
    left = ops.init("left/review-no-apply")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/review-no-apply")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/review-no-apply")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    provider = Task2Provider()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, provider),
    )
    issue_uid = session.current_assessment.issues[0].uid
    session.start_turn(
        "Keep all supported details.", scope="ISSUE", issue_uids=(issue_uid,)
    )
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, provider),
    )
    assert session.state == "READY_TO_APPLY"

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            review_only=True,
        )

    assert action is None
    assert session.state == "READY_TO_APPLY"


def test_meld_compact_surface_arrow_and_apply_row_contract():
    left = ops.init("left/dialogue-input")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/dialogue-input")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/dialogue-input")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )

    with create_pipe_input() as pipe_input:
        option_count = len(session.current_assessment.issues[0].options)
        pipe_input.send_text(
            "\x1b[B\r" + "\x1b[B" * (option_count - 1) + "\r"
        )
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is not None
    assert action.kind == "COMMENT_ALL"
    assert "Choose this reading:" in action.comment
    assert session.current_assessment.issues[0].options[1].text in action.comment


@pytest.mark.parametrize("back_key", ["\x1b", "\x7f"])
def test_meld_compact_back_key_closes_without_saving_a_turn(
    back_key: str,
):
    left = ops.init("left/escape-detail")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/escape-detail")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/escape-detail")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(back_key)
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is None
    assert session.state == "AWAITING_REPLY"


def test_meld_escape_from_overview_closes_without_changing_session():
    left = ops.init("left/escape-overview")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/escape-overview")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/escape-overview")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )
    before = session.to_dict()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is None
    assert session.to_dict() == before


def test_applied_meld_reopens_in_read_only_workbench():
    incoming = ops.init("incoming/applied-view")
    ops.add(incoming, "The Campus Store remains open during construction.")
    baseline = ops.init("baseline/applied-view")
    ops.add(baseline, "The Campus Store remains open during construction.")
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, ZeroChangeDirectionalProvider()),
    )
    change_set = session.prepare_changes()
    session.record_application(
        change_set_digest=change_set.digest,
        checkpoint_uid="00000000-0000-4000-8000-000000000001",
        result_memory_uids=(),
        checkpoints=(
            MeldCheckpointReceipt(
                context_uid=baseline.uid,
                context_name=baseline.name,
                checkpoint_uid="00000000-0000-4000-8000-000000000001",
            ),
        ),
    )
    before = session.to_dict()
    assert "RECOVERY · mem undo" in render_meld_session(session)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        action = run_meld_shell(
            session,
            read_only=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is None
    assert session.to_dict() == before


def test_meld_todo_opens_required_conflict_before_whole_set_resolution():
    left = ops.init("left/global-strategy")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/global-strategy")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/global-strategy")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )
    first_issue_uid = session.current_assessment.issues[0].uid
    original_state = session.state
    navigation = ResolutionNavigation()

    with create_pipe_input() as pipe_input:
        # To Do must route to the first required conflict. A broad whole-set
        # strategy is not an escape hatch around unresolved required items.
        pipe_input.send_text("\x1b[Z\rq")
        action = run_meld_shell(
            session,
            navigation=navigation,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is None
    assert navigation.selected_item_uid == first_issue_uid
    assert session.state == original_state
    assert session.application is None


def test_local_ready_meld_auto_accepts_without_a_review_surface():
    incoming = ops.init("incoming/escape-ready")
    ops.add(incoming, "The Campus Store remains open during construction.")
    baseline = ops.init("baseline/escape-ready")
    ops.add(baseline, "The Campus Store remains open during construction.")
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, ZeroChangeDirectionalProvider()),
    )
    assert session.state == "READY_TO_APPLY"
    before = session.to_dict()

    action = run_meld_shell(
        session,
        app_output=DummyOutput(),
        require_tty=False,
    )

    assert action is not None
    assert action.kind == "ACCEPT"
    assert session.to_dict() == before
    assert session.state == "READY_TO_APPLY"


def test_granted_target_ready_meld_retains_final_review_and_escape_cancels():
    incoming = ops.init("incoming/granted-review")
    ops.add(incoming, "The Campus Store remains open during construction.")
    baseline = ops.init("baseline/granted-review")
    ops.add(baseline, "The Campus Store remains open during construction.")
    session = MeldSession.create_directional(incoming, baseline)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, ZeroChangeDirectionalProvider()),
    )
    session.granted_target = GrantedUpdateTarget(
        public_name="shared/baseline",
        grantee_profile_uid="11111111-1111-4111-8111-111111111111",
        authority_profile_uid="22222222-2222-4222-8222-222222222222",
        attachment_context_uid="attachment-context",
        attachment_context_name="shared",
        grant_uid="33333333-3333-4333-8333-333333333333",
        grant_revision=1,
        grant_digest="a" * 64,
        resource_uid=baseline.uid,
        resource_name=baseline.name,
        authority_context_name=baseline.name,
        permissions=("READ", "UPDATE"),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1bq")
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is None
    assert session.state == "READY_TO_APPLY"


@pytest.mark.parametrize(
    "prefix",
    [
        "\x1b[B\rcUnsent issue comment",
        "gUnsent whole-set comment",
    ],
)
def test_meld_escape_from_composer_discards_unsent_text(prefix):
    left = ops.init("left/escape-composer")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/escape-composer")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/escape-composer")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )
    before = session.to_dict()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(prefix + "\x1bq")
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is None
    assert session.to_dict() == before


def test_meld_resolution_view_sanitizes_option_labels_and_truncates_text():
    left = ops.init("left/safe-screen")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/safe-screen")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/safe-screen")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )
    assessment = session.current_assessment
    assert assessment is not None
    issue = assessment.issues[0]
    unsafe_option = replace(
        issue.options[0],
        label="Keep\x1b[31m\u202edetails",
    )
    safe_issue = replace(
        issue,
        options=(unsafe_option, *issue.options[1:]),
    )
    safe_assessment = replace(
        assessment,
        issues=(safe_issue, *assessment.issues[1:]),
    )
    current_turn = session.current_turn
    assert current_turn is not None
    session.turns = (
        *session.turns[:-1],
        replace(current_turn, assessment=safe_assessment),
    )

    view = MeldResolutionWorkbenchAdapter(session).view()
    navigation = ResolutionNavigation(selected_item_uid=safe_issue.uid)
    navigation.toggle_detail(view)
    rendered = render_resolution_workbench_snapshot(view, navigation=navigation)

    assert "\x1b" not in rendered
    assert "\u202e" not in rendered
    assert "Keep�[31m�details" in rendered
    assert _line("가" * 20, limit=11) == "가" * 5 + "…"


def test_expanded_meld_issue_shows_exact_sources_and_relation_reason():
    left = ops.init("left/detail")
    ops.add(left, "Cash compensation includes travel time.")
    right = ops.init("right/detail")
    ops.add(right, "Use e-transfer or a gift card.")
    target = ops.init("target/detail")
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )
    issue = session.current_assessment.issues[0]

    screen = render_meld_session(
        session,
        expanded_issue_uid=issue.uid,
    )

    assert "SOURCE MEMORIES" in screen
    assert "Cash compensation includes travel time." in screen
    assert "Use e-transfer or a gift card." in screen
    assert "RELATED RELATIONS" in screen
    assert "AFFECTED RESULTS" in screen


def test_atomize_disambiguation_projects_as_directional_issue_meld():
    digest = "0" * 64
    ctx = Context(
        uid="11111111-1111-4111-8111-111111111111",
        name="task/access",
    )
    source = Memory(
        uid="44444444-4444-4444-8444-444444444444",
        content="Students should use a physical card or the app.",
    )
    related = Memory(
        uid="55555555-5555-4555-8555-555555555555",
        content="The staff entrance uses the same NFC.",
    )
    ctx.add(source)
    ctx.add(related)
    bindings = AtomizeGroundingBindings(
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=atomize_grounding_context_digest(ctx),
        analysis_uid="22222222-2222-4222-8222-222222222222",
        analysis_digest=digest,
        workbench_uid="33333333-3333-4333-8333-333333333333",
        workbench_digest=digest,
        response_digest=digest,
    )
    anchor = AtomizeGroundingAnchor(
        issue_uid="ambiguity:physical-card",
        kind="AMBIGUITY",
        arity="UNARY",
        source_uids=("44444444-4444-4444-8444-444444444444",),
        issue_digest=digest,
    )
    session = AtomizeGroundingSession.create(
        bindings=bindings,
        anchor=anchor,
    )
    context_before = ctx.to_dict()
    before = session.to_dict()
    session.start_turn("The entrance accepts only the physical NFC card.")
    view = project_atomize_grounding_as_meld(session, ctx)
    repeated = project_atomize_grounding_as_meld(session, ctx)

    assert view.authority_mode == "DIRECTIONAL"
    assert view.scope == "ISSUE"
    assert view.input_roles == ("INCOMING", "BASELINE")
    incoming, baseline = view.frames
    assert incoming.role == "INCOMING"
    assert incoming.kind == "ISSUE_CONTEXT"
    assert incoming.persistence == "EPHEMERAL"
    assert incoming.source_context_uid is None
    assert incoming.source_context_name is None
    assert incoming.source_context_digest is None
    assert [memory.uid for memory in incoming.memories] == [source.uid]
    assert incoming.memories[0].content == source.content
    assert incoming.memories[0].frame_position == 0
    assert incoming.memories[0].source_position == 0
    assert baseline.role == "BASELINE"
    assert baseline.kind == "CONTAINING_CONTEXT"
    assert baseline.persistence == "BOUND"
    assert baseline.source_context_uid == ctx.uid
    assert baseline.source_context_name == ctx.name
    assert baseline.source_context_digest == bindings.context_digest
    assert [memory.uid for memory in baseline.memories] == [
        source.uid,
        related.uid,
    ]
    assert repeated.frames == view.frames
    assert view.turns[0].revision == "INITIAL"
    assert view.anchor_source_uids == anchor.source_uids
    # The temporary Context is only a projection: neither source artifact is
    # mutated or given a serialized meld field.
    assert ctx.to_dict() == context_before
    assert set(session.to_dict()) == set(before)
    assert "meld" not in session.to_dict()


def test_atomize_pair_issue_preserves_two_memories_in_one_ephemeral_frame():
    digest = "0" * 64
    ctx = Context(
        uid="11111111-1111-4111-8111-111111111111",
        name="task/access",
    )
    first = Memory(
        uid="44444444-4444-4444-8444-444444444444",
        content="The staff entrance uses the same NFC.",
    )
    second = Memory(
        uid="55555555-5555-4555-8555-555555555555",
        content="Only a physical NFC card works at the main entrance.",
    )
    ctx.add(first)
    ctx.add(second)
    session = AtomizeGroundingSession.create(
        bindings=AtomizeGroundingBindings(
            context_uid=ctx.uid,
            context_name=ctx.name,
            context_digest=atomize_grounding_context_digest(ctx),
            analysis_uid="22222222-2222-4222-8222-222222222222",
            analysis_digest=digest,
            workbench_uid="33333333-3333-4333-8333-333333333333",
            workbench_digest=digest,
            response_digest=digest,
        ),
        anchor=AtomizeGroundingAnchor(
            issue_uid="conflict:nfc",
            kind="CONFLICT",
            arity="PAIR",
            source_uids=(first.uid, second.uid),
            issue_digest=digest,
        ),
    )

    view = project_atomize_grounding_as_meld(session, ctx)

    incoming = view.frames[0]
    assert incoming.persistence == "EPHEMERAL"
    assert [memory.uid for memory in incoming.memories] == [
        first.uid,
        second.uid,
    ]
    assert [memory.frame_position for memory in incoming.memories] == [0, 1]


def test_atomize_ephemeral_frame_preserves_slots_without_opening_references():
    digest = "0" * 64
    ctx = Context(
        uid="11111111-1111-4111-8111-111111111111",
        name="task/access",
    )
    first = Memory(
        uid="44444444-4444-4444-8444-444444444444",
        content="The main entrance closes at 5 p.m.",
    )
    secret = Memory(
        uid="66666666-6666-4666-8666-666666666666",
        content="Query-only or referenced content must not enter the frame.",
    )
    reference = MemoryRef(
        uid="77777777-7777-4777-8777-777777777777",
        target_context_uid="88888888-8888-4888-8888-888888888888",
        target_context_name="campus/private",
        target_memory_uid=secret.uid,
        target=secret,
    )
    second = Memory(
        uid="55555555-5555-4555-8555-555555555555",
        content="The rear entrance is closed.",
    )
    ctx.add(first)
    ctx.add(reference)
    ctx.add(second)
    session = AtomizeGroundingSession.create(
        bindings=AtomizeGroundingBindings(
            context_uid=ctx.uid,
            context_name=ctx.name,
            context_digest=atomize_grounding_context_digest(ctx),
            analysis_uid="22222222-2222-4222-8222-222222222222",
            analysis_digest=digest,
            workbench_uid="33333333-3333-4333-8333-333333333333",
            workbench_digest=digest,
            response_digest=digest,
        ),
        anchor=AtomizeGroundingAnchor(
            issue_uid="ambiguity:rear",
            kind="AMBIGUITY",
            arity="UNARY",
            source_uids=(second.uid,),
            issue_digest=digest,
        ),
    )

    view = project_atomize_grounding_as_meld(session, ctx)

    incoming, baseline = view.frames
    assert incoming.memories[0].source_position == 2
    assert [memory.frame_position for memory in baseline.memories] == [0, 1]
    assert [memory.source_position for memory in baseline.memories] == [0, 2]
    assert secret.content not in {
        memory.content for frame in view.frames for memory in frame.memories
    }
