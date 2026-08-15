"""Ownership and recovery boundaries for decision-free semantic application."""

import pytest

from memcommit.application_review_policy import (
    ApplicationReviewPolicy,
    ownership_aware_application_review,
)


def test_local_undoable_mutation_auto_accepts_when_decision_free():
    policy = ownership_aware_application_review(
        mutates_granted_authority=False,
        local_undo_available=True,
    )

    assert policy.decision_free_behavior == "AUTO_ACCEPT"
    assert policy.mutation_boundary == "LOCAL"
    assert policy.recovery == "MEM UNDO"


def test_granted_authority_mutation_retains_final_review_even_with_undo():
    policy = ownership_aware_application_review(
        mutates_granted_authority=True,
        local_undo_available=True,
    )

    assert policy.decision_free_behavior == "FINAL_REVIEW"
    assert policy.mutation_boundary == "GRANTED_AUTHORITY"


def test_local_mutation_without_complete_undo_retains_final_review():
    policy = ownership_aware_application_review(
        mutates_granted_authority=False,
        local_undo_available=False,
    )

    assert policy.decision_free_behavior == "FINAL_REVIEW"
    assert policy.mutation_boundary == "LOCAL"


@pytest.mark.parametrize(
    ("authority", "undo"),
    (("false", True), (False, "yes"), (0, True), (False, 1)),
)
def test_policy_rejects_non_boolean_safety_metadata(authority, undo):
    with pytest.raises(TypeError, match="must be boolean"):
        ownership_aware_application_review(
            mutates_granted_authority=authority,
            local_undo_available=undo,
        )


def test_policy_value_rejects_an_invalid_direct_construction():
    with pytest.raises(ValueError, match="behavior is invalid"):
        ApplicationReviewPolicy(
            decision_free_behavior="SILENT",  # type: ignore[arg-type]
            mutation_boundary="LOCAL",
            recovery="MEM UNDO",
        )
