"""Executable 5 -> 50 Ground authoring replay for the ticker benchmark.

The runner intentionally separates read-only semantic artifacts, Resolve
planning, Resolve application, and ordinary Ground acceptance.  It exposes
only the vague Goal and propositions revealed through the current round to a
provider; host scoring categories and expected-resolution labels stay in the
returned evaluation record.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid

from memcommit.api import MemCommitClient
from memcommit.api.semantic import (
    DistillProposal,
    ElaborateProposal,
    GroundFitReceiptResult,
    GroundResolutionApplyResult,
    GroundResolutionPlanResult,
)
from memcommit.context import Context
from memcommit.eval.ticker_ground_workflow import (
    TickerWorkflowCorpus,
    TickerWorkflowExample,
)
from memcommit.ground import (
    GroundSession,
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_example,
    review_ground_item,
    upgrade_ground_to_propositions,
)
from memcommit.store import MemoryStore, ground_session_record_digest


TICKER_REPLAY_SCHEMA_VERSION = 1
TICKER_REPLAY_RULESET_VERSION = "ticker-ground-replay-v1"
TICKER_REPLAY_GROUND_NAME = "ticker-ground-replay"
TICKER_REFINED_GOAL = (
    "Infer deterministic synthetic ticker rules only from reviewed Examples, "
    "preserve unsupported cases as unresolved, and do not claim official "
    "market symbols."
)

SemanticProviderFactory = Callable[[], object]


class TickerGroundReplayError(ValueError):
    """The replay could not preserve its staged review invariants."""


@dataclass(frozen=True)
class TickerGroundReplayEvent:
    sequence: int
    reveal_round: int
    kind: str
    revision_before: int
    revision_after: int
    mutated: bool
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "reveal_round": self.reveal_round,
            "kind": self.kind,
            "revision_before": self.revision_before,
            "revision_after": self.revision_after,
            "mutated": self.mutated,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class TickerGroundReplayResult:
    corpus_digest: str
    ground_name: str
    ground_uid: str
    final_revision: int
    final_ground_digest: str
    final_goal: str
    final_rules: tuple[str, ...]
    final_example_count: int
    explicit_unresolved_case_ids: tuple[str, ...]
    events: tuple[TickerGroundReplayEvent, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TICKER_REPLAY_SCHEMA_VERSION,
            "ruleset_version": TICKER_REPLAY_RULESET_VERSION,
            "corpus_digest": self.corpus_digest,
            "ground": {
                "name": self.ground_name,
                "uid": self.ground_uid,
                "final_revision": self.final_revision,
                "final_digest": self.final_ground_digest,
                "final_goal": self.final_goal,
                "final_rules": list(self.final_rules),
                "final_example_count": self.final_example_count,
            },
            "explicit_unresolved_case_ids": list(
                self.explicit_unresolved_case_ids
            ),
            "events": [event.to_dict() for event in self.events],
        }


class _ReplayRecorder:
    def __init__(self) -> None:
        self.events: list[TickerGroundReplayEvent] = []

    def add(
        self,
        *,
        reveal_round: int,
        kind: str,
        revision_before: int,
        revision_after: int,
        mutated: bool,
        payload: dict[str, Any],
    ) -> None:
        if mutated != (revision_after != revision_before):
            raise TickerGroundReplayError(
                "Replay mutation labels must match the Ground revision change."
            )
        if mutated and revision_after != revision_before + 1:
            raise TickerGroundReplayError(
                "One reviewed replay action must create exactly one revision."
            )
        self.events.append(
            TickerGroundReplayEvent(
                sequence=len(self.events) + 1,
                reveal_round=reveal_round,
                kind=kind,
                revision_before=revision_before,
                revision_after=revision_after,
                mutated=mutated,
                payload=payload,
            )
        )


def _save_revision(
    store: MemoryStore,
    before: GroundSession,
    after: GroundSession,
) -> None:
    if after.revision != before.revision + 1:
        raise TickerGroundReplayError(
            "A replay Ground mutation must advance exactly one revision."
        )
    store.save_ground_session(
        after,
        replace=True,
        expected_uid=before.uid,
        expected_revision=before.revision,
        expected_digest=ground_session_record_digest(before),
        verify_bound_frames=True,
    )


def _setup_ground(
    store: MemoryStore,
    corpus: TickerWorkflowCorpus,
    *,
    ground_name: str,
) -> tuple[GroundSession, tuple[Context, ...]]:
    names = (
        "evaluation/ticker/description",
        "evaluation/ticker/examples",
        "evaluation/ticker/output",
    )
    contexts = tuple(
        Context(uid=str(uuid.uuid4()), name=name) for name in names
    )
    for context in contexts:
        store.create_context(context)
    raw, examples, output = contexts
    session = bind_ground_workbench(
        create_ground_session(ground_name, goal=corpus.vague_goal),
        description=(
            "Incrementally derive synthetic ticker Rules from only the "
            "reviewed proposition Examples revealed in each benchmark round."
        ),
        raw_context=raw,
        derived_context=examples,
        target_contexts=(output,),
        target_requirements=(
            GroundTargetSpec(
                context_name=output.name,
                description=(
                    "Retain separately reviewed synthetic ticker Rules while "
                    "keeping unsupported cases explicit."
                ),
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    store.save_ground_session(session)
    return session, contexts


def _example_payload(example: TickerWorkflowExample) -> dict[str, object]:
    # Host scoring labels are recorded only after provider-facing execution;
    # they never enter a Distill, Elaborate, or Fit request.
    return {
        "case_id": example.case_id,
        "proposition": example.proposition,
        "role": example.role,
        "resolution": example.resolution,
        "categories": list(example.categories),
    }


def _add_and_accept_example(
    store: MemoryStore,
    session: GroundSession,
    contexts: tuple[Context, ...],
    example: TickerWorkflowExample,
    *,
    reveal_round: int,
    recorder: _ReplayRecorder,
) -> GroundSession:
    proposed = propose_ground_example(
        session,
        proposition=example.proposition,
        rationale=f"Frozen benchmark Example {example.case_id}.",
        current_contexts=contexts,
        input_text=(
            example.company if example.resolution == "DETERMINED" else ""
        ),
        expected_output=example.expected_output,
        case_role=example.role,
        disposition="INCLUDE",
        origin="USER",
    )
    new_example = proposed.items_of_kind("CASE")[-1]
    _save_revision(store, session, proposed)
    recorder.add(
        reveal_round=reveal_round,
        kind="EXAMPLE_PROPOSED",
        revision_before=session.revision,
        revision_after=proposed.revision,
        mutated=True,
        payload={**_example_payload(example), "example_uid": new_example.uid},
    )
    accepted = review_ground_item(
        proposed,
        new_example.uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    _save_revision(store, proposed, accepted)
    recorder.add(
        reveal_round=reveal_round,
        kind="EXAMPLE_ACCEPTED",
        revision_before=proposed.revision,
        revision_after=accepted.revision,
        mutated=True,
        payload={"case_id": example.case_id, "example_uid": new_example.uid},
    )
    return accepted


def _elaborate_payload(proposal: ElaborateProposal) -> dict[str, object]:
    return {
        "analysis_uid": proposal.analysis_uid,
        "mode": proposal.mode,
        "origin": proposal.origin,
        "verification": proposal.verification,
        "overview": proposal.overview,
        "rules": [
            {
                "uid": rule.uid,
                "content": rule.content,
                "rationale": rule.rationale,
            }
            for rule in proposal.rules
        ],
        "cases": [
            {
                "uid": case.uid,
                "proposition": case.proposition,
                "expected": case.expected,
                "rationale": case.rationale,
                "case_role": case.case_role,
                "source_rule_index": case.source_rule_index,
            }
            for case in proposal.cases
        ],
    }


def _distill_payload(proposal: DistillProposal) -> dict[str, object]:
    return {
        "analysis_uid": proposal.analysis_uid,
        "source_context": proposal.source_context,
        "source_digest": proposal.source_digest,
        "goal": proposal.goal,
        "origin": proposal.origin,
        "overview": proposal.overview,
        "rules": [
            {
                "uid": rule.uid,
                "content": rule.content,
                "rationale": rule.rationale,
                "support_memory_uids": list(rule.support_memory_uids),
                "boundary_memory_uids": list(rule.boundary_memory_uids),
            }
            for rule in proposal.rules
        ],
        "outside_memory_uids": list(proposal.outside_memory_uids),
    }


def _fit_payload(receipt: GroundFitReceiptResult) -> dict[str, object]:
    counts: dict[str, int] = {}
    for judgment in receipt.judgments:
        counts[judgment.status] = counts.get(judgment.status, 0) + 1
    return {
        "receipt_uid": receipt.receipt_uid,
        "receipt_digest": receipt.receipt_digest,
        "ground_revision": receipt.ground_revision,
        "ground_digest": receipt.ground_digest,
        "current": receipt.current,
        "overview": receipt.overview,
        "counts": counts,
        "judgments": [
            {
                "example_uid": judgment.example_uid,
                "example_alias": judgment.example_alias,
                "proposition": judgment.proposition,
                "status": judgment.status,
                "reason": judgment.reason,
                "rule_uids": list(judgment.rule_uids),
            }
            for judgment in receipt.judgments
        ],
    }


def _plan_payload(plan: GroundResolutionPlanResult) -> dict[str, object]:
    return {
        "plan_digest": plan.plan_digest,
        "artifact_kind": plan.artifact_kind,
        "artifact_uid": plan.artifact_uid,
        "artifact_digest": plan.artifact_digest,
        "source_verification": plan.source_verification,
        "candidate_verification": plan.candidate_verification,
        "ground_revision": plan.ground_revision,
        "ground_digest": plan.ground_digest,
        "explanation": plan.explanation,
        "action": {
            "kind": plan.action.kind,
            "content": plan.action.content,
            "rationale": plan.action.rationale,
            "selector": plan.action.selector,
            "source_item_uid": plan.action.source_item_uid,
            "case_role": plan.action.case_role,
            "use": plan.action.use,
            "rule_provenance": plan.action.rule_provenance,
        },
    }


def _apply_payload(receipt: GroundResolutionApplyResult) -> dict[str, object]:
    return {
        "plan_digest": receipt.plan_digest,
        "artifact_uid": receipt.artifact_uid,
        "action_kind": receipt.action_kind,
        "previous_revision": receipt.previous_revision,
        "resulting_revision": receipt.resulting_revision,
        "resulting_ground_digest": receipt.resulting_ground_digest,
        "mutated": receipt.mutated,
    }


def _accept_rule_from_plan(
    store: MemoryStore,
    contexts: tuple[Context, ...],
    plan: GroundResolutionPlanResult,
    *,
    reveal_round: int,
    recorder: _ReplayRecorder,
) -> GroundSession:
    session = store.load_ground_session(plan.ground_name)
    if session is None:
        raise TickerGroundReplayError("Resolved Ground disappeared before review.")
    candidates = tuple(
        item
        for item in session.items_of_kind("RULE")
        if item.status == "PROPOSED" and item.content == plan.action.content
    )
    if len(candidates) != 1:
        raise TickerGroundReplayError(
            "Resolve must leave exactly one matching proposed Rule for review."
        )
    accepted = review_ground_item(
        session,
        candidates[0].uid,
        action="ACCEPT",
        current_contexts=contexts,
    )
    _save_revision(store, session, accepted)
    recorder.add(
        reveal_round=reveal_round,
        kind="RULE_ACCEPTED",
        revision_before=session.revision,
        revision_after=accepted.revision,
        mutated=True,
        payload={
            "rule_uid": candidates[0].uid,
            "content": candidates[0].content,
            "source_plan_digest": plan.plan_digest,
        },
    )
    return accepted


def _resolve_candidate(
    client: MemCommitClient,
    store: MemoryStore,
    contexts: tuple[Context, ...],
    source: DistillProposal | ElaborateProposal,
    *,
    candidate_uid: str,
    reveal_round: int,
    recorder: _ReplayRecorder,
) -> GroundSession:
    session = store.load_ground_session(TICKER_REPLAY_GROUND_NAME)
    if session is None:
        raise TickerGroundReplayError("Replay Ground was not found.")
    plan = client.plan_ground_resolution(source, candidate_uid=candidate_uid)
    recorder.add(
        reveal_round=reveal_round,
        kind="RESOLVE_PLANNED",
        revision_before=session.revision,
        revision_after=session.revision,
        mutated=False,
        payload=_plan_payload(plan),
    )
    applied = client.apply_ground_resolution(plan)
    recorder.add(
        reveal_round=reveal_round,
        kind="RESOLVE_APPLIED",
        revision_before=applied.previous_revision,
        revision_after=applied.resulting_revision,
        mutated=applied.mutated,
        payload=_apply_payload(applied),
    )
    return _accept_rule_from_plan(
        store,
        contexts,
        plan,
        reveal_round=reveal_round,
        recorder=recorder,
    )


def _select_distill_rule(
    proposal: DistillProposal,
    session: GroundSession,
) -> str | None:
    active = {
        item.content.casefold()
        for item in session.items_of_kind("RULE")
        if item.status in {"PROPOSED", "ACCEPTED"}
    }
    candidates = tuple(
        rule for rule in proposal.rules if rule.content.casefold() not in active
    )
    if not candidates:
        return None
    selected = max(
        candidates,
        key=lambda rule: (
            len(rule.support_memory_uids) + len(rule.boundary_memory_uids),
            len(rule.support_memory_uids),
            len(rule.content),
            rule.uid,
        ),
    )
    return selected.uid


def _record_fit(
    client: MemCommitClient,
    *,
    reveal_round: int,
    phase: str,
    recorder: _ReplayRecorder,
) -> GroundFitReceiptResult:
    receipt = client.fit_ground(TICKER_REPLAY_GROUND_NAME)
    recorder.add(
        reveal_round=reveal_round,
        kind=f"FIT_{phase}",
        revision_before=receipt.ground_revision,
        revision_after=receipt.ground_revision,
        mutated=False,
        payload=_fit_payload(receipt),
    )
    return receipt


def _refine_goal_from_fit(
    client: MemCommitClient,
    store: MemoryStore,
    receipt: GroundFitReceiptResult,
    *,
    reveal_round: int,
    recorder: _ReplayRecorder,
) -> bool:
    issue = next(
        (judgment for judgment in receipt.judgments if judgment.status != "FIT"),
        None,
    )
    if issue is None:
        return False
    plan = client.plan_ground_resolution(
        receipt,
        example_uid=issue.example_uid,
        action="REVISE_GOAL",
        content=TICKER_REFINED_GOAL,
        rationale=(
            "The first Fit issue shows that the vague Goal does not yet state "
            "the synthetic, evidence-only, unresolved-case boundary."
        ),
    )
    recorder.add(
        reveal_round=reveal_round,
        kind="RESOLVE_GOAL_PLANNED",
        revision_before=receipt.ground_revision,
        revision_after=receipt.ground_revision,
        mutated=False,
        payload=_plan_payload(plan),
    )
    applied = client.apply_ground_resolution(plan)
    recorder.add(
        reveal_round=reveal_round,
        kind="RESOLVE_GOAL_APPLIED",
        revision_before=applied.previous_revision,
        revision_after=applied.resulting_revision,
        mutated=True,
        payload=_apply_payload(applied),
    )
    reopened = client.fit_ground(
        TICKER_REPLAY_GROUND_NAME,
        receipt_uid=receipt.receipt_uid,
    )
    if reopened.current:
        raise TickerGroundReplayError(
            "A successful Goal revision must make the prior Fit receipt stale."
        )
    recorder.add(
        reveal_round=reveal_round,
        kind="FIT_REOPENED_STALE",
        revision_before=applied.resulting_revision,
        revision_after=applied.resulting_revision,
        mutated=False,
        payload=_fit_payload(reopened),
    )
    return store.load_ground_session(TICKER_REPLAY_GROUND_NAME) is not None


def _defer_first_fit_issue(
    client: MemCommitClient,
    receipt: GroundFitReceiptResult,
    *,
    reveal_round: int,
    recorder: _ReplayRecorder,
) -> None:
    issue = next(
        (judgment for judgment in receipt.judgments if judgment.status != "FIT"),
        None,
    )
    if issue is None:
        return
    plan = client.plan_ground_resolution(
        receipt,
        example_uid=issue.example_uid,
        action="DEFER",
        rationale=(
            "Keep this exact Fit issue visible until a separately reviewed "
            "Rule or Example change is available."
        ),
    )
    recorder.add(
        reveal_round=reveal_round,
        kind="RESOLVE_DEFER_PLANNED",
        revision_before=receipt.ground_revision,
        revision_after=receipt.ground_revision,
        mutated=False,
        payload=_plan_payload(plan),
    )
    applied = client.apply_ground_resolution(plan)
    if applied.mutated:
        raise TickerGroundReplayError("Resolve DEFER must not mutate the Ground.")
    recorder.add(
        reveal_round=reveal_round,
        kind="RESOLVE_DEFER_APPLIED",
        revision_before=applied.previous_revision,
        revision_after=applied.resulting_revision,
        mutated=False,
        payload=_apply_payload(applied),
    )


def run_ticker_ground_replay(
    corpus: TickerWorkflowCorpus,
    *,
    root: Path,
    semantic_provider_factory: SemanticProviderFactory,
    ground_name: str = TICKER_REPLAY_GROUND_NAME,
) -> TickerGroundReplayResult:
    """Run the staged workflow and return a complete audit-friendly ledger."""

    if ground_name != TICKER_REPLAY_GROUND_NAME:
        raise TickerGroundReplayError(
            "Ticker replay currently uses one fixed portable Ground name."
        )
    store = MemoryStore(root=root)
    session, contexts = _setup_ground(store, corpus, ground_name=ground_name)
    recorder = _ReplayRecorder()
    recorder.add(
        reveal_round=0,
        kind="GROUND_CREATED",
        revision_before=session.revision,
        revision_after=session.revision,
        mutated=False,
        payload={
            "goal": session.goal,
            "ground_uid": session.uid,
            "ground_digest": ground_session_record_digest(session),
            "bound_contexts": [frame.context_name for frame in session.frames],
        },
    )
    client = MemCommitClient(
        root=root,
        create=False,
        semantic_provider_factory=semantic_provider_factory,
    )
    revealed = 0
    goal_refined = False
    for reveal_round, stage_size in enumerate(corpus.stage_sizes, 1):
        for example in corpus.examples[revealed:stage_size]:
            session = _add_and_accept_example(
                store,
                session,
                contexts,
                example,
                reveal_round=reveal_round,
                recorder=recorder,
            )
        revealed = stage_size

        if reveal_round == 1:
            elaborate = client.elaborate_ground(
                ground_name,
                direction="GOAL_TO_RULES",
            )
            recorder.add(
                reveal_round=reveal_round,
                kind="ELABORATE_GOAL",
                revision_before=session.revision,
                revision_after=session.revision,
                mutated=False,
                payload=_elaborate_payload(elaborate),
            )
            session = _resolve_candidate(
                client,
                store,
                contexts,
                elaborate,
                candidate_uid=elaborate.rules[0].uid,
                reveal_round=reveal_round,
                recorder=recorder,
            )
            early_fit = _record_fit(
                client,
                reveal_round=reveal_round,
                phase="BEFORE_DISTILL",
                recorder=recorder,
            )
            goal_refined = _refine_goal_from_fit(
                client,
                store,
                early_fit,
                reveal_round=reveal_round,
                recorder=recorder,
            )
            if goal_refined:
                session = store.load_ground_session(ground_name)
                if session is None:  # pragma: no cover - checked helper boundary
                    raise TickerGroundReplayError("Replay Ground disappeared.")

        distill = client.distill_ground(ground_name)
        recorder.add(
            reveal_round=reveal_round,
            kind="DISTILL_EXAMPLES",
            revision_before=session.revision,
            revision_after=session.revision,
            mutated=False,
            payload=_distill_payload(distill),
        )
        selected_rule_uid = _select_distill_rule(distill, session)
        if selected_rule_uid is not None:
            session = _resolve_candidate(
                client,
                store,
                contexts,
                distill,
                candidate_uid=selected_rule_uid,
                reveal_round=reveal_round,
                recorder=recorder,
            )
        else:
            recorder.add(
                reveal_round=reveal_round,
                kind="DISTILL_NO_NEW_RULE",
                revision_before=session.revision,
                revision_after=session.revision,
                mutated=False,
                payload={"analysis_uid": distill.analysis_uid},
            )

        elaborated_cases = client.elaborate_ground(
            ground_name,
            direction="RULES_TO_CASES",
        )
        recorder.add(
            reveal_round=reveal_round,
            kind="ELABORATE_RULES",
            revision_before=session.revision,
            revision_after=session.revision,
            mutated=False,
            payload={
                **_elaborate_payload(elaborated_cases),
                "application": (
                    "NOT_APPLIED; frozen benchmark Examples remain authoritative"
                ),
            },
        )
        fit = _record_fit(
            client,
            reveal_round=reveal_round,
            phase="AFTER_DISTILL",
            recorder=recorder,
        )
        _defer_first_fit_issue(
            client,
            fit,
            reveal_round=reveal_round,
            recorder=recorder,
        )

    final = store.load_ground_session(ground_name)
    if final is None:
        raise TickerGroundReplayError("Replay Ground disappeared before verification.")
    if len(final.items_of_kind("CASE")) != len(corpus.examples):
        raise TickerGroundReplayError("Replay did not retain every frozen Example.")
    if any(
        item.status != "ACCEPTED" or item.disposition != "INCLUDE"
        for item in final.items_of_kind("CASE")
    ):
        raise TickerGroundReplayError(
            "Every frozen benchmark Example must remain accepted and included."
        )
    recorder.add(
        reveal_round=len(corpus.stage_sizes),
        kind="FINAL_VERIFICATION",
        revision_before=final.revision,
        revision_after=final.revision,
        mutated=False,
        payload={
            "goal_refined_from_fit": goal_refined,
            "example_count": len(final.items_of_kind("CASE")),
            "rule_count": len(final.items_of_kind("RULE")),
            "all_examples_accepted_and_included": True,
            "explicit_unresolved_case_ids": [
                example.case_id
                for example in corpus.examples
                if example.resolution == "UNRESOLVED"
            ],
        },
    )
    return TickerGroundReplayResult(
        corpus_digest=corpus.digest,
        ground_name=final.contract_name,
        ground_uid=final.uid,
        final_revision=final.revision,
        final_ground_digest=ground_session_record_digest(final),
        final_goal=final.goal,
        final_rules=tuple(
            item.content
            for item in final.items_of_kind("RULE")
            if item.status in {"PROPOSED", "ACCEPTED"}
        ),
        final_example_count=len(final.items_of_kind("CASE")),
        explicit_unresolved_case_ids=tuple(
            example.case_id
            for example in corpus.examples
            if example.resolution == "UNRESOLVED"
        ),
        events=tuple(recorder.events),
    )


__all__ = [
    "TICKER_REFINED_GOAL",
    "TICKER_REPLAY_GROUND_NAME",
    "TICKER_REPLAY_RULESET_VERSION",
    "TICKER_REPLAY_SCHEMA_VERSION",
    "TickerGroundReplayError",
    "TickerGroundReplayEvent",
    "TickerGroundReplayResult",
    "run_ticker_ground_replay",
]
