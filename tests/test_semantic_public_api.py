"""Public Python facade contracts for Distill and Elaborate."""

from __future__ import annotations

import json

import memcommit.ops as ops
from memcommit.api import (
    DistillApplyResult,
    DistillProposal,
    ElaborateProposal,
    FitJudgmentResult,
    FitPropositionInput,
    MemCommitClient,
    SemanticContextError,
    SemanticInputError,
    SemanticProviderFailure,
)
from memcommit.distill import DISTILL_PAYLOAD_MARKER
from memcommit.elaborate import ELABORATE_PAYLOAD_MARKER
from memcommit.fit_judgment import FIT_JUDGMENT_PAYLOAD_MARKER
from memcommit.store import MemoryStore


class SemanticProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert output_schema is not None
        if operation == "fit_propositions":
            payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
            question = payload["questions"][0]
            ids = [
                item["proposition_id"]
                for item in (*question["background"], *question["propositions"])
            ]
            return json.dumps(
                {
                    "overview": "The complete set is compatible.",
                    "judgments": [
                        {
                            "question_id": "fit",
                            "verdict": "YES",
                            "reason": "The Goal and Rule can jointly hold.",
                            "considered_proposition_ids": ids,
                            "material_proposition_ids": [],
                            "consistent_reading": "",
                            "inconsistent_reading": "",
                        }
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
