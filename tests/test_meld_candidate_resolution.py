"""Candidate-based Meld: Audit, Resolve decisions, one Update, then Apply."""

from __future__ import annotations

import json

import pytest

from memcommit.adapters.console.commands.meld.workflow.workflow import (
    _complete_default_terminal_execution,
)
from memcommit.adapters.console.commands.meld.presentation import render_meld_receipt
from memcommit.application.capabilities.semantic_execution import (
    ExecutionStrategy,
)
from memcommit.application.operations.fit.judgment import (
    FIT_JUDGMENT_OPERATION,
    FIT_JUDGMENT_PAYLOAD_MARKER,
)
from memcommit.application.operations.meld.coverage import (
    MELD_COVERAGE_OPERATION,
    MELD_COVERAGE_POLICY,
)
from memcommit.application.operations.meld.model import (
    MELD_CANDIDATE_SCHEMA_VERSION,
    MeldSession,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.preparation import (
    MeldRestartRequest,
    MeldStartRequest,
)
from memcommit.application.operations.meld.resolution import (
    plan_meld_candidate_update,
)
from memcommit.application.operations.meld.runtime import (
    execute_meld_candidate_proposal,
    execute_meld_restart,
    execute_meld_start,
)
from memcommit.application.operations.resolve.decisions import ResolveDecision
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore
import memcommit.persistence.operations.meld.state_repository as meld_state_repository
from memcommit.providers.types import CompletionRun, ProviderIdentity


class _MeldSemanticProvider:
    """One deterministic provider for the complete candidate pipeline."""

    def __init__(
        self,
        calls: list[str],
        conflict_calls: list[int],
        *,
        initial_conflict: bool,
        post_conflict: bool,
        missing_claim: bool,
    ) -> None:
        self.calls = calls
        self.conflict_calls = conflict_calls
        self.initial_conflict = initial_conflict
        self.post_conflict = post_conflict
        self.missing_claim = missing_claim
        self.identity = ProviderIdentity("test", "meld-candidate")
        self.last_run = None

    def _record(self, operation: str) -> None:
        self.calls.append(operation)
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            upstream_model="meld-candidate",
            upstream_provider="test",
        )

    def complete(self, prompt, *, operation, output_schema=None):
        del output_schema
        self._record(operation)
        if operation == FIT_JUDGMENT_OPERATION:
            payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
            aliases = [
                item["proposition_id"]
                for item in payload["questions"][0]["propositions"]
            ]
            return json.dumps(
                {
                    "overview": "The complete candidate can jointly hold.",
                    "judgments": [
                        {
                            "question_id": "fit",
                            "verdict": "YES",
                            "reason": "The complete candidate can jointly hold.",
                            "considered_proposition_ids": aliases,
                            "material_proposition_ids": [],
                            "consistent_reading": "",
                            "inconsistent_reading": "",
                        }
                    ],
                }
            )
        if operation == "find_conflicts":
            self.conflict_calls.append(len(self.conflict_calls) + 1)
            emit = (
                self.initial_conflict
                if len(self.conflict_calls) == 1
                else self.post_conflict
            )
            if not emit:
                return '{"findings":[]}'
            payload = json.loads(prompt.split("QUALITY FIND PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": payload["pairs"][0]["pair_id"],
                            "conflict": "YES",
                            "reason": "The two instructions cannot govern together.",
                            "question": "Which instruction should govern?",
                        }
                    ]
                }
            )
        if operation == "resolve_audit_directions":
            payload = json.loads(prompt.split("RESOLVE AUDIT PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "directions": [
                        {
                            "item_id": item["item_id"],
                            "direction": "Keep the more specific instruction.",
                        }
                        for item in payload["audit"]["items"]
                    ]
                }
            )
        if operation == "update planning":
            assert "The complete candidate already contains every frozen Source claim" in prompt
            return '{"edits":[],"additions":[],"removals":[]}'
        if operation == MELD_COVERAGE_OPERATION:
            payload = json.loads(prompt.split("MELD COVERAGE PAYLOAD:\n", 1)[1])
            results_by_content: dict[str, list[str]] = {}
            for memory in payload["post_image"]:
                results_by_content.setdefault(memory["content"], []).append(
                    memory["result_memory_uid"]
                )
            judgments = []
            for index, claim in enumerate(payload["source_claims"]):
                missing = self.missing_claim and index == 0
                judgments.append(
                    {
                        "claim_id": claim["claim_id"],
                        "status": "MISSING" if missing else "REPRESENTED",
                        "result_memory_uids": (
                            []
                            if missing
                            else [results_by_content[claim["content"]][0]]
                        ),
                        "reason": (
                            "The post-image lost this claim."
                            if missing
                            else "The post-image retains the claim."
                        ),
                    }
                )
            return json.dumps(
                {
                    "overview": "Every frozen Source claim remains represented.",
                    "judgments": judgments,
                }
            )
        assert operation in {"find_duplicates", "find_ambiguities"}
        return '{"findings":[]}'


def _provider_factory(
    *,
    initial_conflict: bool,
    post_conflict: bool,
    missing_claim: bool = False,
):
    calls: list[str] = []
    conflict_calls: list[int] = []

    def factory():
        return _MeldSemanticProvider(
            calls,
            conflict_calls,
            initial_conflict=initial_conflict,
            post_conflict=post_conflict,
            missing_claim=missing_claim,
        )

    return calls, factory


def _contexts(store: MemoryStore) -> tuple[Context, Context, Context]:
    left = Context("10000000-0000-4000-8000-000000000001", "meld/left")
    left.add(
        Memory("10000000-0000-4000-8000-000000000011", "Keep named greetings short.")
    )
    right = Context("20000000-0000-4000-8000-000000000002", "meld/right")
    right.add(
        Memory("20000000-0000-4000-8000-000000000022", "Use punctuation consistently.")
    )
    target = Context("30000000-0000-4000-8000-000000000003", "meld/result")
    for context in (left, right, target):
        store.save(context)
    store.set_current(right.name)
    return left, right, target


def _start_symmetric(store: MemoryStore, provider_factory) -> MeldSession:
    result = execute_meld_start(
        MeldStartRequest(
            mode="SYMMETRIC",
            left_name="meld/left",
            right_name="meld/right",
            target_name="meld/result",
        ),
        store=store,
        provider_factory=provider_factory,
    )
    assert result.origin == "AUDIT_RESOLVE_UPDATE"
    return result.session


def test_meld_starts_from_lossless_candidate_and_full_audit(isolated_store):
    store = MemoryStore()
    left, right, _target = _contexts(store)
    calls, provider_factory = _provider_factory(
        initial_conflict=False,
        post_conflict=False,
    )

    session = _start_symmetric(store, provider_factory)

    assert session.schema_version == MELD_CANDIDATE_SCHEMA_VERSION
    assert session.relation_analysis_seed is None
    assert session.turns == ()
    assert session.candidate_review is not None
    assert tuple(claim.content for claim in session.candidate_review.source_claims) == (
        next(iter(left.memories.values())).content,
        next(iter(right.memories.values())).content,
    )
    assert [
        operation
        for operation in calls
        if operation.startswith("find_") or operation == FIT_JUDGMENT_OPERATION
    ] == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
        FIT_JUDGMENT_OPERATION,
    ]
    encoded = session.to_dict()
    assert "comparison_seed" not in encoded
    assert MeldSession.from_dict(encoded).to_dict() == encoded


def test_exact_restart_reuses_the_existing_candidate_audit(isolated_store):
    store = MemoryStore()
    _contexts(store)
    calls, provider_factory = _provider_factory(
        initial_conflict=False,
        post_conflict=False,
    )
    first = _start_symmetric(store, provider_factory)
    prior_calls = tuple(calls)

    restarted = execute_meld_restart(
        MeldRestartRequest(
            mode="SYMMETRIC",
            left_name="meld/left",
            right_name="meld/right",
            target_name="meld/result",
            expected_version=meld_canonical_digest(first.to_dict()),
        ),
        store=store,
        provider_factory=provider_factory,
    ).session

    assert restarted.uid != first.uid
    assert restarted.candidate_review is not None
    assert first.candidate_review is not None
    assert restarted.candidate_review.candidate.uid == first.candidate_review.candidate.uid
    assert restarted.candidate_review.audit.uid == first.candidate_review.audit.uid
    assert tuple(calls) == prior_calls


def test_no_issue_meld_still_runs_one_update_then_applies_verified_postimage(
    isolated_store,
):
    store = MemoryStore()
    _left, _right, target = _contexts(store)
    calls, provider_factory = _provider_factory(
        initial_conflict=False,
        post_conflict=False,
    )
    session = _start_symmetric(store, provider_factory)
    before = meld_canonical_digest(session.to_dict())

    proposal = plan_meld_candidate_update(
        session,
        (),
        target=store.load_direct(target.name),
        update_provider_factory=provider_factory,
        audit_provider_factory=provider_factory,
        direction_provider_factory=provider_factory,
        coverage_provider_factory=provider_factory,
    )
    applied, receipt = execute_meld_candidate_proposal(
        session,
        proposal,
        store=store,
        expected_session_digest=before,
    )

    assert calls.count("update planning") == 1
    assert calls.count("find_conflicts") == 2
    assert calls.count(MELD_COVERAGE_OPERATION) == 1
    assert proposal.ready_to_apply
    assert receipt.applied
    assert applied.state == "APPLIED"
    assert [memory.content for memory in store.load_direct(target.name).memories.values()] == [
        "Keep named greetings short.",
        "Use punctuation consistently.",
    ]


def test_console_no_issue_candidate_goes_directly_to_applied_receipt_state(
    isolated_store,
):
    store = MemoryStore()
    _contexts(store)
    _calls, provider_factory = _provider_factory(
        initial_conflict=False,
        post_conflict=False,
    )
    session = _start_symmetric(store, provider_factory)

    completed = _complete_default_terminal_execution(
        store=store,
        session=session,
        provider_factory=provider_factory,
    )

    assert completed.state == "APPLIED"


def test_new_postimage_conflict_opens_another_resolve_round_without_apply(
    isolated_store,
):
    store = MemoryStore()
    _left, _right, target = _contexts(store)
    calls, provider_factory = _provider_factory(
        initial_conflict=False,
        post_conflict=True,
    )
    session = _start_symmetric(store, provider_factory)
    before = meld_canonical_digest(session.to_dict())

    proposal = plan_meld_candidate_update(
        session,
        (),
        target=store.load_direct(target.name),
        update_provider_factory=provider_factory,
        audit_provider_factory=provider_factory,
        direction_provider_factory=provider_factory,
        coverage_provider_factory=provider_factory,
    )
    retained, receipt = execute_meld_candidate_proposal(
        session,
        proposal,
        store=store,
        expected_session_digest=before,
    )

    assert not proposal.ready_to_apply
    assert not receipt.applied
    assert receipt.next_round == 1
    assert retained.candidate_review is not None
    assert retained.candidate_review.round == 1
    assert {issue.kind for issue in retained.candidate_review.issues} == {"CONFLICT"}
    assert tuple(store.load_direct(target.name).iter_items()) == ()
    assert calls.count("resolve_audit_directions") == 1


def test_force_is_explicit_unresolved_state_and_does_not_reopen_same_item(
    isolated_store,
):
    store = MemoryStore()
    _left, _right, target = _contexts(store)
    _calls, provider_factory = _provider_factory(
        initial_conflict=True,
        post_conflict=True,
    )
    session = _start_symmetric(store, provider_factory)
    assert session.candidate_review is not None
    assert len(session.candidate_review.issues) == 1
    issue = session.candidate_review.issues[0]

    proposal = plan_meld_candidate_update(
        session,
        (ResolveDecision(issue.uid, "FORCE"),),
        target=store.load_direct(target.name),
        update_provider_factory=provider_factory,
        audit_provider_factory=provider_factory,
        direction_provider_factory=provider_factory,
        coverage_provider_factory=provider_factory,
    )
    applied, receipt = execute_meld_candidate_proposal(
        session,
        proposal,
        store=store,
        expected_session_digest=meld_canonical_digest(session.to_dict()),
    )

    assert proposal.blocking_audit_keys == ()
    assert proposal.next_review is None
    assert receipt.applied
    assert applied.candidate_review is not None
    assert applied.candidate_review.forced_audit_keys == (issue.audit_key,)
    assert "UNRESOLVED · 1" in render_meld_receipt(applied)


def test_missing_source_coverage_blocks_target_publication(isolated_store):
    store = MemoryStore()
    _left, _right, target = _contexts(store)
    _calls, provider_factory = _provider_factory(
        initial_conflict=False,
        post_conflict=False,
        missing_claim=True,
    )
    session = _start_symmetric(store, provider_factory)

    proposal = plan_meld_candidate_update(
        session,
        (),
        target=store.load_direct(target.name),
        update_provider_factory=provider_factory,
        audit_provider_factory=provider_factory,
        direction_provider_factory=provider_factory,
        coverage_provider_factory=provider_factory,
    )
    unchanged, receipt = execute_meld_candidate_proposal(
        session,
        proposal,
        store=store,
        expected_session_digest=meld_canonical_digest(session.to_dict()),
    )

    assert not proposal.ready_to_apply
    assert not receipt.applied
    assert receipt.missing_claim_aliases == ("s1",)
    assert unchanged is session
    assert tuple(store.load_direct(target.name).iter_items()) == ()


def test_applied_session_write_failure_rolls_back_target_and_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _left, _right, target = _contexts(store)
    _calls, provider_factory = _provider_factory(
        initial_conflict=False,
        post_conflict=False,
    )
    session = _start_symmetric(store, provider_factory)
    version = meld_canonical_digest(session.to_dict())
    target_before = store.load_direct(target.name).to_dict()
    checkpoints_before = store.list_checkpoints(target.name)
    proposal = plan_meld_candidate_update(
        session,
        (),
        target=store.load_direct(target.name),
        update_provider_factory=provider_factory,
        audit_provider_factory=provider_factory,
        direction_provider_factory=provider_factory,
        coverage_provider_factory=provider_factory,
    )
    session_path = store._meld_session_path(target.uid)
    write = meld_state_repository._write_json_atomic
    failed = {"value": False}

    def fail_applied_session(path, value):
        if (
            path == session_path
            and value.get("state") == "APPLIED"
            and not failed["value"]
        ):
            failed["value"] = True
            raise OSError("injected applied-session failure")
        return write(path, value)

    monkeypatch.setattr(
        meld_state_repository,
        "_write_json_atomic",
        fail_applied_session,
    )

    with pytest.raises(OSError, match="injected applied-session failure"):
        execute_meld_candidate_proposal(
            session,
            proposal,
            store=store,
            expected_session_digest=version,
        )

    assert failed["value"]
    assert store.load_direct(target.name).to_dict() == target_before
    assert store.list_checkpoints(target.name) == checkpoints_before
    retained = store.load_meld_session(target.uid)
    assert retained is not None
    assert retained.state == "AWAITING_REPLY"
    assert meld_canonical_digest(retained.to_dict()) == version
    assert session.state == "AWAITING_REPLY"


def test_candidate_coverage_remains_one_whole_frame_contract():
    assert MELD_COVERAGE_POLICY.strategy is ExecutionStrategy.WHOLE_FRAME_ONLY
    assert not MELD_COVERAGE_POLICY.staged_supported
