"""Operation-neutral frozen-resolution contract tests."""

from __future__ import annotations

import pytest

from memcommit.resolution import (
    ResolutionAttempt,
    ResolutionBinding,
    ResolutionCase,
    ResolutionRequirement,
    ResolutionSubmission,
    ResolutionValidationError,
    evaluate_resolution,
    require_resolution_ready,
)


def _case() -> ResolutionCase:
    return ResolutionCase(
        binding=ResolutionBinding(
            operation="example",
            artifact_uid="artifact-1",
            revision="revision-1",
        ),
        requirements=(
            ResolutionRequirement("required-a", ("KEEP", "TAKE")),
            ResolutionRequirement("required-b", ("KEEP", "TAKE")),
            ResolutionRequirement(
                "optional-note",
                (),
                obligation="OPTIONAL",
                comment_allowed=True,
            ),
        ),
    )


def test_evaluation_orders_answers_by_the_frozen_case_and_tracks_required_items():
    case = _case()

    progress = evaluate_resolution(
        case,
        ResolutionAttempt(
            binding=case.binding,
            submissions=(
                ResolutionSubmission(
                    "optional-note",
                    comment="Reviewed separately.",
                ),
                ResolutionSubmission("required-b", choice_uid="TAKE"),
            ),
        ),
    )

    assert [item.item_uid for item in progress.submissions] == [
        "required-b",
        "optional-note",
    ]
    assert progress.unresolved_required_uids == ("required-a",)
    assert progress.ready is False


def test_optional_items_do_not_block_a_complete_required_resolution():
    progress = require_resolution_ready(
        _case(),
        ResolutionAttempt(
            binding=_case().binding,
            submissions=(
                ResolutionSubmission("required-a", choice_uid="KEEP"),
                ResolutionSubmission("required-b", choice_uid="TAKE"),
            ),
        ),
    )

    assert progress.ready is True
    assert [item.item_uid for item in progress.submissions] == [
        "required-a",
        "required-b",
    ]


@pytest.mark.parametrize(
    ("submissions", "code", "item_uid"),
    [
        (
            (ResolutionSubmission("unknown", choice_uid="KEEP"),),
            "UNKNOWN_ITEM",
            "unknown",
        ),
        (
            (
                ResolutionSubmission("required-a", choice_uid="KEEP"),
                ResolutionSubmission("required-a", choice_uid="TAKE"),
            ),
            "DUPLICATE_ITEM",
            "required-a",
        ),
        (
            (ResolutionSubmission("required-a", choice_uid="OTHER"),),
            "UNAVAILABLE_CHOICE",
            "required-a",
        ),
        (
            (ResolutionSubmission("required-a", comment="Use another value."),),
            "COMMENT_NOT_ALLOWED",
            "required-a",
        ),
    ],
)
def test_evaluation_rejects_uid_or_capability_crossing_submissions(
    submissions,
    code,
    item_uid,
):
    with pytest.raises(ResolutionValidationError) as raised:
        case = _case()
        evaluate_resolution(
            case,
            ResolutionAttempt(binding=case.binding, submissions=submissions),
        )

    assert raised.value.code == code
    assert raised.value.item_uids == (item_uid,)


def test_bulk_resolution_is_all_or_nothing_across_the_frozen_requirements():
    case = ResolutionCase(
        binding=ResolutionBinding("merge", "artifact", "revision"),
        requirements=(
            ResolutionRequirement("one", ("KEEP", "TAKE")),
            ResolutionRequirement("two", ("KEEP",)),
        ),
    )

    with pytest.raises(ResolutionValidationError) as raised:
        require_resolution_ready(
            case,
            ResolutionAttempt(binding=case.binding, bulk_choice_uid="TAKE"),
        )

    assert raised.value.code == "UNAVAILABLE_CHOICE"
    assert raised.value.item_uids == ("two",)
    assert raised.value.choice_uid == "TAKE"


def test_readiness_failure_preserves_every_missing_required_identity():
    with pytest.raises(ResolutionValidationError) as raised:
        case = _case()
        require_resolution_ready(
            case,
            ResolutionAttempt(
                binding=case.binding,
                submissions=(ResolutionSubmission("optional-note", comment="Noted."),),
            ),
        )

    assert raised.value.code == "UNRESOLVED_REQUIRED"
    assert raised.value.item_uids == ("required-a", "required-b")


def test_empty_case_is_already_ready_without_fabricating_a_decision():
    case = ResolutionCase(
        binding=ResolutionBinding("merge", "artifact", "revision"),
        requirements=(),
    )

    progress = require_resolution_ready(
        case,
        ResolutionAttempt(binding=case.binding, bulk_choice_uid="KEEP"),
    )

    assert progress.ready is True
    assert progress.submissions == ()


def test_attempt_must_match_the_complete_frozen_binding():
    case = _case()
    stale = ResolutionAttempt(
        binding=ResolutionBinding(
            operation=case.binding.operation,
            artifact_uid=case.binding.artifact_uid,
            revision="older-revision",
        ),
        submissions=(ResolutionSubmission("required-a", choice_uid="KEEP"),),
    )

    with pytest.raises(ResolutionValidationError) as raised:
        evaluate_resolution(case, stale)

    assert raised.value.code == "STALE_BINDING"
