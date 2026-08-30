"""Operation-level contracts for exact saved Meld responses."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import memcommit.application.operations.meld.proposal_iteration as resolution_application
from memcommit.application.operations.meld.proposal_iteration import (
    MeldResolutionError,
    MeldResolutionTurnRequest,
    meld_resolution_case,
    prepare_meld_resolution_turn,
)
from memcommit.application.operations.meld.proposal_iteration import MeldSessionSnapshot


def _snapshot() -> MeldSessionSnapshot:
    issues = (
        SimpleNamespace(
            uid="issue-required",
            priority="REQUIRED",
            options=(
                SimpleNamespace(uid="option-a", text="Preserve A."),
                SimpleNamespace(uid="option-b", text="Preserve B."),
            ),
        ),
        SimpleNamespace(
            uid="issue-helpful",
            priority="HELPFUL",
            options=(SimpleNamespace(uid="option-c", text="Clarify C."),),
        ),
    )
    return MeldSessionSnapshot(
        session=SimpleNamespace(
            uid="meld-session-1",
            current_assessment=SimpleNamespace(issues=issues),
        ),
        version_token="saved-version-1",
    )


def test_meld_projects_exact_issue_choices_and_obligations() -> None:
    case = meld_resolution_case(_snapshot())

    assert case.binding.operation == "meld"
    assert case.binding.artifact_uid == "meld-session-1"
    assert case.binding.revision == "saved-version-1"
    assert [requirement.item_uid for requirement in case.requirements] == [
        "issue-required",
        "issue-helpful",
    ]
    assert case.requirements[0].choice_uids == ("option-a", "option-b")
    assert case.requirements[0].obligation == "REQUIRED"
    assert case.requirements[1].obligation == "OPTIONAL"
    assert all(requirement.comment_allowed for requirement in case.requirements)


def test_exact_option_uid_is_translated_only_inside_the_meld_operation(
    monkeypatch,
) -> None:
    captured = []

    def prepare(request):
        captured.append(request)
        return SimpleNamespace(session="pending", expected_version="saved-version-1")

    monkeypatch.setattr(resolution_application, "prepare_meld_turn", prepare)

    pending = prepare_meld_resolution_turn(
        MeldResolutionTurnRequest(
            snapshot=_snapshot(),
            issue_uid="issue-required",
            option_uid="option-b",
            comment="Use the source wording.",
        )
    )

    assert pending.session == "pending"
    assert captured[0].scope == "ISSUE"
    assert captured[0].issue_uids == ("issue-required",)
    assert captured[0].comment == (
        "Choose this reading: Preserve B.\n\nUse the source wording."
    )
    assert captured[0].snapshot.version_token == "saved-version-1"


def test_incremental_issue_response_does_not_require_every_required_issue(
    monkeypatch,
) -> None:
    captured = []
    monkeypatch.setattr(
        resolution_application,
        "prepare_meld_turn",
        lambda request: (captured.append(request) or SimpleNamespace(session="ok")),
    )

    result = prepare_meld_resolution_turn(
        MeldResolutionTurnRequest(
            snapshot=_snapshot(),
            issue_uid="issue-helpful",
            comment="Please clarify this optional point.",
        )
    )

    assert result.session == "ok"
    assert captured[0].comment == "Please clarify this optional point."


@pytest.mark.parametrize(
    ("issue_uid", "option_uid", "message"),
    (
        ("missing", None, "unknown current issue"),
        ("issue-required", "missing", "unavailable issue option"),
        (None, "option-a", "requires one exact issue"),
    ),
)
def test_invalid_exact_response_is_rejected_before_turn_composition(
    issue_uid,
    option_uid,
    message,
) -> None:
    with pytest.raises(MeldResolutionError, match=message):
        prepare_meld_resolution_turn(
            MeldResolutionTurnRequest(
                snapshot=_snapshot(),
                issue_uid=issue_uid,
                option_uid=option_uid,
                comment="" if option_uid is not None else "Explain.",
            )
        )


def test_whole_set_response_requires_comment() -> None:
    with pytest.raises(MeldResolutionError, match="requires a comment"):
        prepare_meld_resolution_turn(MeldResolutionTurnRequest(snapshot=_snapshot()))
