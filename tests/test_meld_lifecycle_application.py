"""Terminal-free lifecycle contracts for Meld assessment and saved sessions."""

from __future__ import annotations

from types import SimpleNamespace

import memcommit.meld_assessment_application as assessment_application
import memcommit.meld_session_application as session_application
from memcommit.meld_assessment_application import (
    FrozenMeldAssessment,
    run_meld_assessment,
)
from memcommit.meld_session_application import (
    MeldSessionSnapshot,
    MeldTurnRequest,
    prepare_meld_turn,
)


class _Session:
    def __init__(self):
        self.current_turn = SimpleNamespace(uid="turn-1")
        self.recorded = None
        self.started = None

    def to_dict(self):
        return {"session": "one"}

    def record_assessment(self, turn_uid, assessment):
        self.recorded = (turn_uid, assessment)

    def start_turn(self, comment, **kwargs):
        self.started = (comment, kwargs)


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
