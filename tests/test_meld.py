"""End-to-end contracts for Context-to-Context symmetric meld."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.atomize_grounding import (
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingSession,
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
from memcommit.context import Context, MemoryRef
from memcommit.commands.meld import render_meld_session
from memcommit.commands.meld_shell import (
    _line,
    _screen_text,
    run_meld_shell,
)
from memcommit.meld import (
    MeldError,
    MeldSession,
    meld_canonical_digest,
)
from memcommit.meld_provider import MELD_PAYLOAD_MARKER, assess_meld_turn
from memcommit.provenance import build_trace
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
)


runner = CliRunner()


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
                            "The rate and travel-time condition come from "
                            "Ian's policy."
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
        payload = json.loads(
            prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1]
        )
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
                                    "Keep the in-person and online "
                                    "policies as separately scoped rules."
                                ),
                            },
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


def _task2_contexts(
    store: MemoryStore,
    *,
    with_comparison: bool = True,
):
    left = ops.init("ian/proposal-writing-policy")
    ops.add(
        left,
        (
            "Budget CAD 20–30 per hour in cash, including participation and "
            "travel time."
        ),
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
    assert [
        relation.uid for relation in session.current_assessment.relations
    ] == [relation.uid for relation in comparison.relations]
    assert [issue.uid for issue in session.current_assessment.issues] == [
        issue.uid for issue in comparison.issues
    ]

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
    assert "Budget CAD 20–30 per hour in cash" in (
        meld_event.declared_frame or ""
    )

    second_accept = runner.invoke(
        app,
        ["meld", left.name, right.name, "--accept"],
    )
    assert second_accept.exit_code == 0
    assert "no duplicate checkpoint" in second_accept.output
    assert len(store.list_checkpoints(target.name)) == 1
    assert len(provider.payloads) == 1


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

    assert value["schema_version"] == 2
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
    bad_import["turns"][0]["assessment"]["relations"][0][
        "summary"
    ] = "A forged imported relation."
    with pytest.raises(MeldError, match="turn zero does not match"):
        MeldSession.from_dict(bad_import)


def test_defer_all_is_provider_free_and_does_not_mutate_target(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    left, right, target = _task2_contexts(store)
    provider = Task2Provider()
    _patch_provider(monkeypatch, provider)
    assert runner.invoke(
        app,
        ["meld", left.name, right.name],
    ).exit_code == 0
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
    assert runner.invoke(
        app,
        ["meld", left.name, right.name, "--defer-all"],
    ).exit_code == 0
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


def test_preserve_all_is_one_semantic_round_and_remains_non_applying(
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
    assert runner.invoke(
        app,
        ["meld", left.name, right.name],
    ).exit_code == 0
    before = store._context_file(target.name).read_bytes()

    result = runner.invoke(
        app,
        ["meld", left.name, right.name, "--preserve-all"],
    )

    assert result.exit_code == 0, result.output
    assert len(provider.payloads) == 1
    assert provider.payloads[-1]["current_turn"]["scope"] == "REMAINING"
    assert "READY_TO_APPLY" in result.output
    assert result.output.count("[PRESERVE]") == 2
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
    user_add = next(
        item for item in proposals if item["disposition"] == "USER_ADD"
    )
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
    assert runner.invoke(
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
    ).exit_code == 0
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
    assert runner.invoke(
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
    ).exit_code == 0
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
    assert runner.invoke(
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
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["meld", left.name, right.name, "--accept"],
    ).exit_code == 0
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
    duplicate_source["frames"][1]["context_uid"] = (
        duplicate_source["frames"][0]["context_uid"]
    )
    with pytest.raises(MeldError, match="Duplicate meld source"):
        MeldSession.from_dict(duplicate_source)

    cross_peer_distinct = session.to_dict()
    cross_peer_distinct["turns"][0]["assessment"]["relations"][0][
        "kind"
    ] = "DISTINCT"
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
    session = MeldSession.create_symmetric(left, right, target)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, Task2Provider()),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\r\r\tKeep all supported details.\x13"
        )
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is not None
    assert action.kind == "COMMENT_ISSUE"
    assert action.choice_index == 0
    assert action.comment == "Keep all supported details."
    assert action.issue_uid == session.current_assessment.issues[0].uid


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
            "\r\r\tKeep the rate.\nKeep every payment method.\r"
        )
        action = run_meld_shell(
            session,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action is not None
    assert action.kind == "COMMENT_ISSUE"
    assert action.choice_index == 0
    assert action.comment == (
        "Keep the rate.\nKeep every payment method."
    )


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
    bindings = AtomizeGroundingBindings(
        context_uid="11111111-1111-4111-8111-111111111111",
        context_name="task/access",
        context_digest=digest,
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
    before = session.to_dict()
    session.start_turn("The entrance accepts only the physical NFC card.")
    view = project_atomize_grounding_as_meld(session)

    assert view.authority_mode == "DIRECTIONAL"
    assert view.scope == "ISSUE"
    assert view.input_roles == ("CLARIFICATION", "BASELINE")
    assert view.turns[0].revision == "INITIAL"
    assert view.anchor_source_uids == anchor.source_uids
    # The adapter is lossless metadata over the existing strict schema.
    assert set(session.to_dict()) == set(before)
    assert "meld" not in session.to_dict()
