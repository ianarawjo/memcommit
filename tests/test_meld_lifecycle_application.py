"""Terminal-free lifecycle contracts for Meld assessment and saved sessions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import memcommit.application.operations.semantic_updates.curate_integrate.meld.planning as assessment_application
import memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_iteration as session_application
from memcommit.application.operations.semantic_updates.curate_integrate.meld.planning import (
    FrozenMeldAssessment,
    run_meld_assessment,
)
from memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_iteration import (
    MeldSessionSnapshot,
    MeldSessionVersionError,
    MeldTurnRequest,
    prepare_meld_turn,
    require_meld_session_version,
)


class _Session:
    def __init__(self):
        self.current_turn = SimpleNamespace(uid="turn-1")
        self.recorded = None
        self.started = None
        self.state = "AWAITING_REPLY"
        self.application = None

    def to_dict(self):
        return {"session": "one"}

    def record_assessment(self, turn_uid, assessment):
        self.recorded = (turn_uid, assessment)

    def start_turn(self, comment, **kwargs):
        self.started = (comment, kwargs)

    def clear_application(self, **kwargs):
        self.cleared = kwargs
        self.state = "READY_TO_APPLY"
        self.application = None


class _AssessmentPort:
    def __init__(self):
        self.commit_values = None

    def commit(self, frozen, **values):
        self.commit_values = (frozen, values)
        return values["session"]


def test_cached_assessment_never_constructs_a_provider(monkeypatch):
    original = _Session()
    candidate = _Session()
    assessment = object()
    monkeypatch.setattr(
        assessment_application.MeldSession,
        "from_dict",
        lambda value: candidate,
    )
    monkeypatch.setattr(
        assessment_application,
        "assess_meld_turn",
        lambda session, provider: assessment,
    )
    port = _AssessmentPort()

    result = run_meld_assessment(
        FrozenMeldAssessment(
            session=original,
            expected_session_digest="version-1",
            cached_completion="saved response",
            token=object(),
        ),
        port=port,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("cache hit connected a provider")
        ),
    )

    assert result.origin == "CACHE"
    assert result.session is candidate
    assert candidate.recorded == ("turn-1", assessment)
    assert port.commit_values[1]["completion"] is None


def test_provider_assessment_captures_completion_before_commit(monkeypatch):
    original = _Session()
    candidate = _Session()
    assessment = object()
    provider = SimpleNamespace(
        identity="provider-id",
        complete=lambda *args, **kwargs: "provider response",
    )
    monkeypatch.setattr(
        assessment_application.MeldSession,
        "from_dict",
        lambda value: candidate,
    )

    def assess(session, capturing_provider):
        capturing_provider.complete("prompt", operation="meld_contexts")
        return assessment

    monkeypatch.setattr(assessment_application, "assess_meld_turn", assess)
    port = _AssessmentPort()

    result = run_meld_assessment(
        FrozenMeldAssessment(
            session=original,
            expected_session_digest="version-1",
            cached_completion=None,
            token=object(),
        ),
        port=port,
        provider_factory=lambda: provider,
    )

    assert result.origin == "PROVIDER"
    assert port.commit_values[1]["completion"] == "provider response"
    assert port.commit_values[1]["origin_provider"] == "provider-id"


def test_prepare_turn_clones_saved_session_and_retains_cas_token(monkeypatch):
    original = _Session()
    candidate = _Session()
    monkeypatch.setattr(
        session_application.MeldSession,
        "from_dict",
        lambda value: candidate,
    )

    pending = prepare_meld_turn(
        MeldTurnRequest(
            snapshot=MeldSessionSnapshot(original, "version-1"),
            comment="Use the reviewed interpretation.",
            scope="ISSUE",
            issue_uids=("issue-1",),
        )
    )

    assert pending.session is candidate
    assert pending.expected_version == "version-1"
    assert original.started is None
    assert candidate.started == (
        "Use the reviewed interpretation.",
        {
            "scope": "ISSUE",
            "issue_uids": ("issue-1",),
            "revision": "EXTEND",
            "revises_turn_uids": (),
        },
    )


def test_saved_mutation_requires_the_exact_reviewed_version():
    snapshot = MeldSessionSnapshot(_Session(), "version-1")

    assert require_meld_session_version(snapshot, "version-1") is snapshot
    with pytest.raises(MeldSessionVersionError, match="changed"):
        require_meld_session_version(snapshot, "older-version")


def test_apply_retry_accepts_only_the_reconstructed_reviewed_predecessor(
    monkeypatch,
):
    applied = _Session()
    applied.state = "APPLIED"
    applied.application = SimpleNamespace(
        change_set_digest="change-set",
        checkpoint_uid="checkpoint-1",
        checkpoints=(),
    )
    reviewed = _Session()
    monkeypatch.setattr(
        session_application.MeldSession,
        "from_dict",
        lambda value: reviewed,
    )
    monkeypatch.setattr(
        session_application,
        "meld_canonical_digest",
        lambda value: "reviewed-version",
    )
    snapshot = MeldSessionSnapshot(applied, "applied-version")

    assert (
        require_meld_session_version(
            snapshot,
            "reviewed-version",
            allow_applied_predecessor=True,
        )
        is snapshot
    )
    assert reviewed.cleared == {
        "change_set_digest": "change-set",
        "checkpoint_uid": "checkpoint-1",
        "checkpoints": (),
    }
    with pytest.raises(MeldSessionVersionError):
        require_meld_session_version(snapshot, "reviewed-version")
