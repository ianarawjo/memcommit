"""Distill Goal Fit contract tests."""

from __future__ import annotations

import json

import pytest

from memcommit.application.operations.semantic_updates.derive.distill.goal_fit import (
    DISTILL_GOAL_FIT_OPERATION,
    DISTILL_GOAL_FIT_PAYLOAD_MARKER,
    DistillGoalFitError,
    DistillGoalFitRule,
    audit_distill_goal_fit,
)


RULES = (
    DistillGoalFitRule(
        uid="00000000-0000-4000-8000-000000000001",
        content="Prefer a quiet setting for conversation.",
    ),
    DistillGoalFitRule(
        uid="00000000-0000-4000-8000-000000000002",
        content="Confirm the final setting with the user.",
    ),
)


class GoalFitProvider:
    def __init__(self, *, verdict="FIT", considered=None, material=None):
        self.verdict = verdict
        self.considered = considered
        self.material = material
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == DISTILL_GOAL_FIT_OPERATION
        assert output_schema is not None
        self.calls += 1
        payload = json.loads(prompt.split(DISTILL_GOAL_FIT_PAYLOAD_MARKER, 1)[1])
        aliases = [rule["rule_id"] for rule in payload["rules"]]
        material = self.material
        if material is None:
            material = [] if self.verdict == "FIT" else aliases[:1]
        return json.dumps(
            {
                "verdict": self.verdict,
                "reason": "The complete proposed Rule set was audited.",
                "considered_rule_ids": (
                    aliases if self.considered is None else self.considered
                ),
                "material_rule_ids": material,
            }
        )


def test_goal_fit_audits_every_rule_without_turning_goal_into_evidence():
    provider = GoalFitProvider(verdict="FIT")

    audit = audit_distill_goal_fit(
        "Recommend a conversation setting.",
        RULES,
        provider=provider,
    )

    assert audit.verdict == "FIT"
    assert audit.considered_rule_uids == tuple(rule.uid for rule in RULES)
    assert audit.material_rule_uids == ()
    assert provider.calls == 1


def test_goal_fit_keeps_not_fit_material_rule_identity():
    provider = GoalFitProvider(verdict="NOT_FIT", material=["r000002"])

    audit = audit_distill_goal_fit(
        "Recommend a conversation setting.",
        RULES,
        provider=provider,
    )

    assert audit.verdict == "NOT_FIT"
    assert audit.material_rule_uids == (RULES[1].uid,)


def test_goal_fit_rejects_nonexhaustive_provider_coverage():
    provider = GoalFitProvider(verdict="FIT", considered=["r000001"])

    with pytest.raises(DistillGoalFitError, match="omitted, duplicated, or reordered"):
        audit_distill_goal_fit(
            "Recommend a conversation setting.",
            RULES,
            provider=provider,
        )


def test_goal_fit_empty_rule_set_is_deterministically_fit_without_provider():
    provider = GoalFitProvider()

    audit = audit_distill_goal_fit(
        "Recommend a conversation setting.",
        (),
        provider=provider,
    )

    assert audit.verdict == "FIT"
    assert audit.considered_rule_uids == ()
    assert provider.calls == 0
