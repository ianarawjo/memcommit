"""Public Python facade contracts for Distill and Elaborate."""

from __future__ import annotations

import json
import uuid

import memcommit.ops as ops
import pytest
from memcommit.api import (
    DistillApplyResult,
    DistillProposal,
    ElaborateProposal,
    FitJudgmentResult,
    FitPropositionInput,
    GroundFitReceiptResult,
    GroundResolutionApplyResult,
    GroundResolutionPlanResult,
    MemCommitClient,
    SemanticContextError,
    SemanticInputError,
    SemanticProviderFailure,
)
from memcommit.distill import DISTILL_PAYLOAD_MARKER
from memcommit.elaborate import ELABORATE_PAYLOAD_MARKER
from memcommit.fit_judgment import FIT_JUDGMENT_PAYLOAD_MARKER
from memcommit.context import Context
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_example,
    propose_ground_rule,
    upgrade_ground_to_propositions,
)
from memcommit.store import MemoryStore


class SemanticProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert output_schema is not None
        if operation == "fit_propositions":
            payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
            return json.dumps(
                {
                    "overview": "The complete set is compatible.",
                    "judgments": [
                        {
                            "question_id": question["question_id"],
                            "verdict": (
                                "YES"
                                if question["question_id"] == "fit"
                                else "MAY"
                            ),
                            "reason": (
                                "The Goal and Rule can jointly hold."
                                if question["question_id"] == "fit"
                                else "The Rule lacks a single-word algorithm."
                            ),
                            "considered_proposition_ids": [
                                item["proposition_id"]
                                for item in (
                                    *question["background"],
                                    *question["propositions"],
                                )
                            ],
                            "material_proposition_ids": (
                                []
                                if question["question_id"] == "fit"
                                else [
                                    item["proposition_id"]
                                    for item in question["propositions"]
                                ]
                            ),
                            "consistent_reading": (
                                ""
                                if question["question_id"] == "fit"
                                else "A plausible mnemonic could be RED."
                            ),
                            "inconsistent_reading": (
                                ""
                                if question["question_id"] == "fit"
                                else "A different plausible mnemonic could be RWD."
                            ),
                        }
                        for question in payload["questions"]
                    ],
                }
            )
        if operation == "distill_context":
            payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
            aliases = [item["memory_id"] for item in payload["source"]["memories"]]
            return json.dumps(
                {
                    "overview": "One evidence-bound Rule is supported.",
                    "rules": [
                        {
                            "content": "Confirm the option before acting.",
                            "rationale": "The Source proposition supports it.",
                            "support_memory_ids": aliases,
                            "boundary_memory_ids": [],
                        }
                    ],
                    "outside_memory_ids": [],
                }
            )
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        if payload["mode"] == "GOAL_TO_RULES":
            return json.dumps(
                {
                    "overview": "One Rule makes the Goal reviewable.",
                    "rules": [
                        {
                            "content": "Confirm the option before acting.",
                            "rationale": "This operationalizes the Goal.",
                        }
                    ],
                }
            )
        return json.dumps(
            {
                "overview": "One Case makes the Rule testable.",
                "cases": [
                    {
                        "proposition": "The person explicitly confirms option A.",
                        "expected": "Proceed with A.",
                        "rationale": "This is a fitting Case.",
                        "case_role": "FIT",
                        "source_rule_index": 1,
                    }
                ],
            }
        )


def _source(root):
    store = MemoryStore(root=root)
    context = ops.init("semantic/source")
    ops.add(context, "The person confirmed option A before it was used.")
    store.save(context)
    store.set_current(context.name)
    return store, context


def _ground_source(root):
    store = MemoryStore(root=root)
    description = Context(
        uid=str(uuid.uuid4()),
        name="semantic/ground-description",
    )
    examples = Context(
        uid=str(uuid.uuid4()),
        name="semantic/ground-examples",
    )
    output = Context(
        uid=str(uuid.uuid4()),
        name="semantic/ground-output",
    )
    for context in (description, examples, output):
        store.create_context(context)
    contexts = (description, examples, output)
    session = bind_ground_workbench(
        create_ground_session(
            "semantic-ground",
            goal="티커가 어떻게 만들어지는지 규칙을 알고 싶어",
        ),
        description="Refine synthetic ticker Rules from reviewed Examples.",
        raw_context=description,
        derived_context=examples,
        target_contexts=(output,),
        target_requirements=(
            GroundTargetSpec(
                context_name=output.name,
                description="Retain reviewed ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    session = propose_ground_rule(
        session,
        rule="Use one initial per meaningful company-name token.",
        rationale="Start with an intentionally incomplete Rule.",
        current_contexts=contexts,
    )
    session = propose_ground_example(
        session,
        proposition=(
            'Applying the synthetic ticker Rules to "Redwood Inc." '
            'produces "RED".'
        ),
        rationale="A single-word boundary Example.",
        current_contexts=contexts,
        case_role="BOUNDARY",
    )
    store.save_ground_session(session)
    return store, session


def test_public_distill_returns_typed_proposal_and_exact_apply(isolated_store):
    store, source = _source(isolated_store)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=SemanticProvider,
    )

    proposal = client.distill_context(source.name, goal="Confirm before acting.")
    receipt = client.apply_distill(proposal, output_name="semantic/rules")

    assert isinstance(proposal, DistillProposal)
    assert proposal.rules[0].support_memory_uids == tuple(source.memories)
    assert isinstance(receipt, DistillApplyResult)
    assert store.context_exists("semantic/rules")
    assert store.load_direct(source.name).to_dict() == source.to_dict()


def test_public_elaborate_uses_one_typed_entry_for_both_directions(isolated_store):
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=SemanticProvider,
    )

    goal = client.elaborate(goal="Confirm before acting.")
    rules = client.elaborate(rules=("Confirm the option before acting.",))

    assert isinstance(goal, ElaborateProposal)
    assert goal.mode == "GOAL_TO_RULES"
    assert goal.verification == "UNVERIFIED"
    assert rules.mode == "RULES_TO_CASES"
    assert rules.cases[0].case_role == "FIT"


def test_public_fit_accepts_role_typed_propositions_without_store_effect(
    isolated_store,
):
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=SemanticProvider,
    )

    result = client.fit(
        (
            FitPropositionInput("Keep the entrance usable.", "GOAL", "goal"),
            FitPropositionInput("Use the staff entrance.", "RULE", "rule"),
        )
    )

    assert isinstance(result, FitJudgmentResult)
    assert result.verdict == "YES"
    assert result.considered_aliases == ("goal", "rule")
    assert result.propositions[0].role == "GOAL"


def test_public_elaborate_rejects_ambiguous_direction_without_provider(
    isolated_store,
):
    calls = 0

    def provider():
        nonlocal calls
        calls += 1
        return SemanticProvider()

    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=provider,
    )

    try:
        client.elaborate(goal="A Goal", rules=("A Rule",))
    except SemanticInputError:
        pass
    else:
        raise AssertionError("ambiguous Elaborate input must fail")
    assert calls == 0


def test_public_semantic_provider_failure_uses_stable_error(isolated_store):
    class FailingProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            raise RuntimeError("provider transport failed")

    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=FailingProvider,
    )

    try:
        client.elaborate(goal="Confirm before acting.")
    except SemanticProviderFailure as error:
        assert "provider transport failed" in str(error)
    else:
        raise AssertionError("provider failure must cross the public taxonomy")


def test_public_ground_semantics_classify_missing_ground_as_context_error(
    isolated_store,
):
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=SemanticProvider,
    )

    for invoke in (
        lambda: client.distill_ground("missing-ground"),
        lambda: client.elaborate_ground(
            "missing-ground",
            direction="GOAL_TO_RULES",
        ),
    ):
        try:
            invoke()
        except SemanticContextError as error:
            assert "was not found" in str(error)
        else:
            raise AssertionError("a missing Ground must use the public context error")


def test_public_ground_elaborate_resolve_keeps_plan_and_apply_separate(
    isolated_store,
):
    store, session = _ground_source(isolated_store)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=SemanticProvider,
    )

    proposal = client.elaborate_ground(
        session.contract_name,
        direction="GOAL_TO_RULES",
    )
    plan = client.plan_ground_resolution(
        proposal,
        candidate_uid=proposal.rules[0].uid,
    )

    assert isinstance(plan, GroundResolutionPlanResult)
    assert plan.artifact_kind == "ELABORATE"
    assert plan.source_verification == "UNVERIFIED"
    assert plan.candidate_verification == "UNVERIFIED"
    assert plan.action.kind == "PROPOSE_RULE"
    assert store.load_ground_session(session.contract_name) == session

    receipt = client.apply_ground_resolution(plan)

    assert isinstance(receipt, GroundResolutionApplyResult)
    assert receipt.mutated is True
    assert receipt.previous_revision == session.revision
    assert receipt.resulting_revision == session.revision + 1
    saved = store.load_ground_session(session.contract_name)
    assert saved is not None
    assert saved.items_of_kind("RULE")[-1].content == proposal.rules[0].content
    assert saved.items_of_kind("RULE")[-1].status == "PROPOSED"


def test_public_ground_fit_resolve_stales_the_old_receipt(isolated_store):
    store, session = _ground_source(isolated_store)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=SemanticProvider,
    )

    fit = client.fit_ground(session.contract_name)
    rule = session.items_of_kind("RULE")[0]
    example = session.items_of_kind("CASE")[0]

    assert isinstance(fit, GroundFitReceiptResult)
    assert fit.current is True
    assert fit.judgments[0].status == "UNDERDETERMINED"
    plan = client.plan_ground_resolution(
        fit,
        example_uid=example.uid,
        action="REFINE_RULE",
        rule_uid=rule.uid,
        content=(
            "For a normalized single-word name, use its first three "
            "alphabetic characters in uppercase."
        ),
        rationale="The Redwood boundary needs a deterministic algorithm.",
    )
    client.apply_ground_resolution(plan)

    reopened = client.fit_ground(
        session.contract_name,
        receipt_uid=fit.receipt_uid,
    )
    assert reopened.current is False
    assert reopened.receipt_uid == fit.receipt_uid
    saved = store.load_ground_session(session.contract_name)
    assert saved is not None
    assert saved.revision == session.revision + 1


def test_public_ground_distill_resolve_retains_evidence_bound_status(
    isolated_store,
):
    store, session = _ground_source(isolated_store)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=SemanticProvider,
    )

    proposal = client.distill_ground(session.contract_name)
    plan = client.plan_ground_resolution(
        proposal,
        candidate_uid=proposal.rules[0].uid,
    )

    assert plan.artifact_kind == "DISTILL"
    assert plan.source_verification == "EVIDENCE_BOUND"
    assert plan.candidate_verification == "EVIDENCE_BOUND"
    assert plan.action.source_item_uid == proposal.rules[0].uid
    assert store.load_ground_session(session.contract_name) == session

    receipt = client.apply_ground_resolution(plan)
    assert receipt.resulting_revision == session.revision + 1
    saved = store.load_ground_session(session.contract_name)
    assert saved is not None
    assert saved.items_of_kind("RULE")[-1].content == proposal.rules[0].content


def test_public_resolve_rejects_standalone_semantic_proposal(isolated_store):
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=SemanticProvider,
    )
    proposal = client.elaborate(goal="Confirm before acting.")

    with pytest.raises(SemanticInputError, match="Ground Elaborate"):
        client.plan_ground_resolution(
            proposal,
            candidate_uid=proposal.rules[0].uid,
        )
