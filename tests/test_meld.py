"""End-to-end contracts for Context-to-Context symmetric meld."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.commands.meld as meld_command
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
    analyze_comparison,
)
from memcommit.comparison_store import (
    comparison_analysis_path,
    load_comparison_analysis,
    save_comparison_analysis,
)
from memcommit.context import Context, Memory, MemoryRef
from memcommit.commands.compare import render_comparison
from memcommit.commands.meld import render_meld_session
from memcommit.commands.meld_shell import (
    MeldShellAction,
    _comparison_issue_resolution_badges,
    _line,
    _screen_text,
    run_meld_shell,
)
from memcommit.commands.resolution_workbench_shell import (
    _viewer_focus_fragments,
    RESOLUTION_WORKBENCH_STYLE,
    ResolutionGlobalStrategy,
    _seeded_report_lines,
    _seeded_report_sections,
    resolution_seeded_report_fragments,
)
from memcommit.meld import (
    MeldError,
    MeldSession,
    meld_canonical_digest,
    meld_accounting,
)
from memcommit.meld_provider import (
    MELD_PAYLOAD_MARKER,
    assess_meld_turn,
    meld_output_schema,
)
from memcommit.responses.model import ResponseDraft
from memcommit.meld_resolution_adapter import MeldResolutionWorkbenchAdapter
from memcommit.provenance import build_trace
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
)


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
        "_start_new_meld_from_picker",
        lambda selected_store: started.append(selected_store),
    )

    meld_command._browse_saved_meld_sessions(store)

    assert started == [store]


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

    meld_command._start_new_meld_from_picker(store)

    assert calls == [
        {
            "left": "incoming",
            "into": "baseline",
            "left_descendants": False,
            "right_descendants": False,
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
            "relations",
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
                            "kind": "CONFLICT",
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

        assert current["scope"] == "ISSUE"
        assert current["issue_ids"] == ["i000001"]
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

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
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

    reviewed = meld_command._load_symmetric_comparison(
        left=left_scope,
        right=right_scope,
        target=target,
        create_target=True,
        include_descendants=(True, True),
    )
    session = MeldSession.create_symmetric_from_comparison(reviewed, target)
    restored = MeldSession.from_dict(session.to_dict())

    assert restored.comparison_seed is not None
    assert restored.comparison_seed.analysis.include_descendants == (True, True)
    assert tuple(frame.include_descendants for frame in restored.frames) == (
        True,
        True,
    )
    assert any(
        "[scope/left/child]" in memory.content for memory in restored.frames[0].memories
    )


def test_directional_meld_freezes_incoming_descendants_but_direct_baseline(
    isolated_store,
):
    store = MemoryStore()
    incoming = ops.init("direction/incoming")
    incoming_child = ops.init("direction/incoming/child")
    ops.add(incoming_child, "Child-owned incoming evidence.")
    baseline = ops.init("direction/baseline")
    ops.add(baseline, "Direct authoritative baseline.")
    for context in (incoming, incoming_child, baseline):
        store.create_context(context)

    incoming_scope = meld_command._load_local_meld_source(
        store,
        incoming.name,
        include_descendants=True,
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
    assert any(
        "[direction/incoming/child]" in memory.content
        for memory in restored.frames[0].memories
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
            relations = payload["previous"]["relations"]
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
        ["meld", left.name, right.name],
    )
    assert initial.exit_code == 0, initial.output
    assert len(provider.payloads) == 0
    assert "MEM MELD · SYMMETRIC" in initial.output
    assert "Compare:" in initial.output
    assert "· IMPORTED" in initial.output
    assert "Participant compensation policy" in initial.output
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

    resumed = runner.invoke(app, ["meld", left.name, right.name])
    assert resumed.exit_code == 0, resumed.output
    assert len(provider.payloads) == 0
    assert "Resumed without calling the semantic provider" in resumed.output

    grounded = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
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
    assert "State: READY_TO_APPLY" in grounded.output
    assert "CAD 20–30" in grounded.output
    assert "cash" in grounded.output
    assert "e-transfer" in grounded.output
    assert "gift card" in grounded.output
    assert store._context_file(target.name).read_bytes() == target_before
    ready_session = store.load_meld_session(target.uid)
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
        ["meld", left.name, right.name, "--accept"],
    )
    assert applied.exit_code == 0, applied.output
    assert len(provider.payloads) == 1
    assert "Applied 2 meld results" in applied.output
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
        ["meld", left.name, right.name, "--accept"],
    )
    assert second_accept.exit_code == 0
    assert "no duplicate checkpoint" in second_accept.output
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

    assert runner.invoke(app, ["meld", left.name, right.name]).exit_code == 0
    grounded = runner.invoke(
        app,
        [
            "meld",
            left.name,
            right.name,
            "--issue",
            "1",
            "--choice",
            "1",
            "--comment",
            "Keep all supported details.",
        ],
    )
    assert grounded.exit_code == 0, grounded.output
    applied = runner.invoke(app, ["meld", left.name, right.name, "--accept"])
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


def test_symmetric_meld_requires_saved_compare_before_provider_connection(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(
        store,
        with_comparison=False,
    )

    def unexpected_provider_factory():
        raise AssertionError("Meld connected a provider before Compare.")

    monkeypatch.setattr(
        "memcommit.commands.meld.connect_codex_chatgpt_provider",
        unexpected_provider_factory,
    )
    target_before = store._context_file(target.name).read_bytes()

    result = runner.invoke(app, ["meld", left.name, right.name])

    assert result.exit_code == 1
    assert "requires a saved Compare analysis" in result.output
    assert f"mem switch {left.name}" in result.output
    assert f"mem compare --to {right.name}" in result.output
    assert f"mem switch {target.name}" in result.output
    assert store.load_meld_session(target.uid) is None
    assert store._context_file(target.name).read_bytes() == target_before


def test_symmetric_meld_rejects_stale_or_reverse_only_compare(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)

    def unexpected_provider_factory():
        raise AssertionError("Meld connected a provider for an invalid basis.")

    monkeypatch.setattr(
        "memcommit.commands.meld.connect_codex_chatgpt_provider",
        unexpected_provider_factory,
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

    stale = runner.invoke(app, ["meld", left.name, right.name])

    assert stale.exit_code == 1
    assert "is stale" in stale.output
    assert "--refresh" in stale.output
    assert store.load_meld_session(target.uid) is None

    fresh_left = store.load_direct(left.name)
    comparison_analysis_path(left.uid, right.uid).unlink()
    _save_task2_comparison(store, right, fresh_left)
    reverse_only = runner.invoke(
        app,
        ["meld", left.name, right.name],
    )

    assert reverse_only.exit_code == 1
    assert "requires a saved Compare analysis" in reverse_only.output
    assert store.load_meld_session(target.uid) is None


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
    assert "MEM MELD · DIRECTIONAL" in result.output
    assert (
        "INCOMING test/update/from → BASELINE / TARGET test/update/to"
    ) in result.output
    assert "State: READY_TO_APPLY" in result.output
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
    assert (
        "mem meld test/update/from --into test/update/to --accept" in shorthand.output
    )
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
    assert "~  1. [EDIT · SYNTHESIZE]" in initial.output
    assert "+  2. [ADD · PRESERVE]" in initial.output
    assert store.list_checkpoints(baseline.name) == []

    applied = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )

    assert applied.exit_code == 0, applied.output
    assert "Applied 2 meld changes" in applied.output
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
    assert record["schema_version"] == 2
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
    assert "no duplicate checkpoint" in repeated.output
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
    assert "Recovered the prior meld application" in recovered.output
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
    assert "State: READY_TO_APPLY" in initial.output
    assert "no material baseline changes" in initial.output

    applied = runner.invoke(
        app,
        ["meld", incoming.name, "--into", baseline.name, "--accept"],
    )

    assert applied.exit_code == 0, applied.output
    assert "Applied 0 meld changes" in applied.output
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
    assert "no duplicate checkpoint" in repeated.output
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
    assert "Recovered the prior meld application" in recovered.output
    assert len(store.list_checkpoints(baseline.name)) == 1
    assert store.load_meld_session(baseline.uid).state == "APPLIED"
    assert len(provider.payloads) == 1


def test_directional_meld_grammar_help_and_to_boundary(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    incoming, baseline, _, _ = _directional_contexts(store)

    class UnexpectedProvider:
        def complete(self, *args, **kwargs):
            raise AssertionError("Invalid meld grammar called the provider.")

    _patch_provider(monkeypatch, UnexpectedProvider())

    help_result = runner.invoke(app, ["meld", "--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "--into" in help_result.output
    assert "--from" in help_result.output
    assert "--to" in help_result.output
    assert "authoritative BASELINE" in help_result.output
    assert "normalized to INCOMING" in help_result.output

    missing_peers = runner.invoke(
        app,
        ["meld", "--to", baseline.name],
    )
    assert missing_peers.exit_code == 1
    assert "requires LEFT and RIGHT Contexts" in missing_peers.output

    too_many = runner.invoke(
        app,
        ["meld", incoming.name, baseline.name, "--into", baseline.name],
    )
    assert too_many.exit_code == 1
    assert "accepts at most one positional INCOMING" in too_many.output

    missing_peer = runner.invoke(app, ["meld", incoming.name])
    assert missing_peer.exit_code == 1
    assert "requires LEFT and RIGHT Contexts" in missing_peer.output

    same_context = runner.invoke(
        app,
        ["meld", incoming.name, "--into", incoming.name],
    )
    assert same_context.exit_code == 1
    assert "distinct" in same_context.output
    assert "INCOMING" in same_context.output
    assert "BASELINE" in same_context.output


def test_symmetric_meld_to_creates_empty_result_without_switching(
    isolated_store,
):
    store = MemoryStore()
    left, right, current = _task2_contexts(store)
    result_name = "task-2/participant/proposal-workspace"

    result = runner.invoke(
        app,
        ["meld", left.name, right.name, "--to", result_name],
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


def test_symmetric_meld_to_never_adopts_existing_or_leaves_failed_target(
    isolated_store,
):
    store = MemoryStore()
    left, right, existing = _task2_contexts(store, with_comparison=False)

    occupied = runner.invoke(
        app,
        ["meld", left.name, right.name, "--to", existing.name],
    )
    assert occupied.exit_code == 1
    assert "already exists" in occupied.output
    assert store.load_meld_session(existing.uid) is None

    missing_name = "task-2/participant/missing-compare-result"
    missing_compare = runner.invoke(
        app,
        ["meld", left.name, right.name, "--to", missing_name],
    )
    assert missing_compare.exit_code == 1
    assert "requires a saved Compare analysis" in missing_compare.output
    assert not store.context_exists(missing_name)
    assert f"--to {missing_name}" in missing_compare.output


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
    assert "INCOMING and BASELINE must be distinct" in same_context.output

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
            ["meld", left.name, right.name],
        ).exit_code
        == 0
    )
    before = store._context_file(target.name).read_bytes()

    deferred = runner.invoke(
        app,
        ["meld", left.name, right.name, "--defer-all"],
    )

    assert deferred.exit_code == 0
    assert "KEPT_REVIEW_ONLY" in deferred.output
    assert len(provider.payloads) == 0
    assert store._context_file(target.name).read_bytes() == before
    assert store.list_checkpoints(target.name) == []


def test_deferred_session_restart_requires_exact_ordered_compare_basis(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(app, ["meld", left.name, right.name]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["meld", left.name, right.name, "--defer-all"],
        ).exit_code
        == 0
    )
    deferred = store.load_meld_session(target.uid)
    assert deferred is not None

    failed = runner.invoke(
        app,
        ["meld", right.name, left.name, "--restart"],
    )
    assert failed.exit_code == 1
    assert "requires a saved Compare analysis" in failed.output
    still_deferred = store.load_meld_session(target.uid)
    assert still_deferred is not None
    assert still_deferred.uid == deferred.uid

    reverse = _save_task2_comparison(store, right, left)
    restarted = runner.invoke(
        app,
        ["meld", right.name, left.name, "--restart"],
    )

    assert restarted.exit_code == 0, restarted.output
    assert len(provider.payloads) == 0
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
    left, right, _ = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(app, ["meld", left.name, right.name]).exit_code == 0

    resumed = runner.invoke(app, ["meld", right.name, left.name])

    assert resumed.exit_code == 0, resumed.output
    assert "Resumed without calling the semantic provider" in resumed.output
    assert len(provider.payloads) == 0


def test_revision_flags_require_a_semantic_comment_or_choice(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, _ = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(app, ["meld", left.name, right.name]).exit_code == 0

    result = runner.invoke(
        app,
        ["meld", left.name, right.name, "--revision", "correct"],
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
            ["meld", left.name, right.name],
        ).exit_code
        == 0
    )
    before = store._context_file(target.name).read_bytes()

    result = runner.invoke(
        app,
        ["meld", left.name, right.name, "--preserve-all"],
    )

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 0
    assert "READY_TO_APPLY" in result.output
    assert result.output.count("[PRESERVE]") == 2
    assert "Source coverage: 2/2" in result.output
    assert "Cross-relation results: 0" in result.output
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
    initial = runner.invoke(app, ["meld", left.name, right.name])
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
    assert runner.invoke(app, ["meld", left.name, right.name]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "meld",
                left.name,
                right.name,
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
        ["meld", left.name, right.name, "--accept"],
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
    assert runner.invoke(app, ["meld", left.name, right.name]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "meld",
                left.name,
                right.name,
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
        ["meld", left.name, right.name, "--accept"],
    )
    assert interrupted.exit_code == 1
    assert len(store.list_checkpoints(target.name)) == 1
    assert len(tuple(store.load_direct(target.name).iter_items())) == 2
    persisted = store.load_meld_session(target.uid)
    assert persisted is not None
    assert persisted.state == "READY_TO_APPLY"

    recovered = runner.invoke(
        app,
        ["meld", left.name, right.name, "--accept"],
    )

    assert recovered.exit_code == 0, recovered.output
    assert "Recovered the prior meld application" in recovered.output
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
    assert runner.invoke(app, ["meld", left.name, right.name]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "meld",
                left.name,
                right.name,
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
            ["meld", left.name, right.name, "--accept"],
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
        ["meld", left.name, right.name, "--accept"],
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
    schema = meld_output_schema(4, mode=mode)
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


def test_meld_shell_selects_one_issue_reading_and_free_form_comment():
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
        pipe_input.send_text(
            "\t\x1b[B\r\t\r\x1b[B\x1b[B\x1b[B\r"
            "Keep all supported details.\x13\t\t\r\x1b[F\r"
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
    assert "Keep all supported details." in action.comment
    assert comparison.issues[0].title in action.comment


def test_ready_meld_applies_after_the_shared_final_review_screen():
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
        # To Do opens Review and Apply; the final Enter confirms the exact
        # ready proposal.
        pipe_input.send_text("\x1b[Z\r\x1b[F\r")
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
        pipe_input.send_text("aq")
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            review_only=True,
        )

    assert action is None
    assert session.state == "READY_TO_APPLY"


def test_meld_framed_composer_matches_ground_send_and_newline_contract():
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
        pipe_input.send_text(
            "\t\x1b[B\r\t\r\x1b[B\x1b[B\x1b[B\r"
            "Keep the rate.\nKeep every payment method.\r\t\t\r\x1b[F\r"
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
    assert "Keep the rate.\nKeep every payment method." in action.comment


@pytest.mark.parametrize("back_key", ["\x1b", "\x7f"])
def test_meld_back_key_collapses_detail_before_leaving_the_workbench(
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
        # Tab reaches Items and Down selects conflict 1. Either back key returns
        # to REPORT instead of closing, then the conflict can be selected again.
        pipe_input.send_text(
            f"\t\x1b[B\r{back_key}\x1b[B\rcStill reviewing.\x13\t\t\r\x1b[F\r"
        )
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is not None
    assert action.kind == "COMMENT_ALL"
    assert "Other direction: Still reviewing." in action.comment


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
    )
    before = session.to_dict()

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


def test_meld_escape_never_implicitly_accepts_a_ready_session():
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


def test_meld_screen_sanitizes_option_labels_and_truncates_by_cell_width():
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

    rendered = "".join(
        text
        for _style, text in _screen_text(
            session,
            selected_index=0,
            expanded=True,
            choice_index=None,
        )
    )

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
