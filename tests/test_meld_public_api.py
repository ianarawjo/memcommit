"""Stable Python facade coverage for terminal-independent Meld."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import memcommit.adapters.python_api._operations.meld as meld_operation
from memcommit.adapters.python_api import (
    MeldConflictError,
    MeldContextError,
    MeldSessionResult,
    MeldStorageError,
    MemCommitClient,
)
from memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_iteration import MeldSessionSnapshot


def _review_session():
    option = SimpleNamespace(uid="option-1", label="Keep both", text="Keep both.")
    issue = SimpleNamespace(
        uid="issue-1",
        priority="REQUIRED",
        title="Resolve wording",
        question="Which wording?",
        why_it_matters="It changes the result.",
        options=(option,),
    )
    proposal = SimpleNamespace(
        uid="proposal-1",
        operation="EDIT",
        disposition="SYNTHESIZE",
        content="Reviewed content.",
        reason="Both sources support it.",
    )
    assessment = SimpleNamespace(
        overview="One complete reviewed Meld.",
        ready_to_apply=False,
        issues=(issue,),
        proposals=(proposal,),
    )
    session = SimpleNamespace(
        uid="session-1",
        mode="DIRECTIONAL",
        frames=(
            SimpleNamespace(context_name="incoming"),
            SimpleNamespace(context_name="baseline"),
        ),
        target=SimpleNamespace(context_name="baseline"),
        state="AWAITING_REPLY",
        turns=(object(),),
        current_assessment=assessment,
        application=None,
    )
    session.to_dict = lambda: {"uid": session.uid, "state": session.state}
    return session


def test_start_meld_projects_runtime_session_without_terminal_state(
    tmp_path,
    monkeypatch,
):
    session = _review_session()
    calls = []

    def execute(request, **kwargs):
        calls.append((request, kwargs))
        return SimpleNamespace(session=session, origin="PROVIDER")

    monkeypatch.setattr(meld_operation, "execute_meld_start", execute)
    client = MemCommitClient(
        root=tmp_path / "store",
        create=True,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("facade adapter unexpectedly connected a provider")
        ),
    )

    result = client.start_meld("incoming", "baseline")

    assert isinstance(result, MeldSessionResult)
    assert result.session_uid == "session-1"
    assert result.origin == "PROVIDER"
    assert result.issues[0].options[0].label == "Keep both"
    assert calls[0][0].mode == "DIRECTIONAL"


def test_restart_meld_forwards_the_reviewed_version(monkeypatch, tmp_path):
    session = _review_session()
    calls = []

    def execute(request, **kwargs):
        calls.append((request, kwargs))
        return SimpleNamespace(session=session, origin="EXACT_PREWARM")

    monkeypatch.setattr(meld_operation, "execute_meld_restart", execute)
    client = MemCommitClient(
        root=tmp_path / "store",
        create=True,
        semantic_provider_factory=lambda: object(),
    )

    result = client.restart_meld(
        "incoming",
        "baseline",
        "baseline",
        expected_version="saved-version",
    )

    assert result.origin == "EXACT_PREWARM"
    assert calls[0][0].expected_version == "saved-version"
    assert calls[0][0].mode == "DIRECTIONAL"


def test_open_meld_maps_missing_target_to_public_context_error(tmp_path):
    client = MemCommitClient(root=tmp_path / "store", create=True)

    with pytest.raises(MeldContextError):
        client.open_meld("missing")


def test_remaining_meld_lifecycle_methods_delegate_to_the_operation_owner(
    tmp_path,
    monkeypatch,
):
    client = MemCommitClient(root=tmp_path / "store", create=True)
    calls = []

    def capture(name):
        def invoke(*args, **kwargs):
            calls.append((name, args, kwargs))
            return name

        return invoke

    for name in ("comment_meld", "preserve_meld", "defer_meld", "apply_meld"):
        monkeypatch.setattr(meld_operation, name, capture(name))

    assert (
        client.comment_meld(
            "result",
            "Keep both.",
            issue_uid="issue-1",
            option_uid="option-1",
            expected_version="saved-version",
            revision="replace",
            revises_turn_uids=("turn-1",),
        )
        == "comment_meld"
    )
    assert (
        client.preserve_meld("result", expected_version="saved-version")
        == "preserve_meld"
    )
    assert client.defer_meld("result", expected_version="saved-version") == "defer_meld"
    assert client.apply_meld("result", expected_version="saved-version") == "apply_meld"

    assert calls[0][1][0] is client._runtime
    assert calls[0][1][1:] == ("result", "Keep both.")
    assert calls[0][2] == {
        "issue_uid": "issue-1",
        "option_uid": "option-1",
        "expected_version": "saved-version",
        "revision": "replace",
        "revises_turn_uids": ("turn-1",),
    }
    assert [call[0] for call in calls] == [
        "comment_meld",
        "preserve_meld",
        "defer_meld",
        "apply_meld",
    ]
    assert [call[2]["expected_version"] for call in calls] == [
        "saved-version",
        "saved-version",
        "saved-version",
        "saved-version",
    ]


def test_comment_meld_rejects_a_stale_review_before_provider_connection(
    tmp_path,
    monkeypatch,
):
    session = _review_session()
    monkeypatch.setattr(
        meld_operation,
        "_meld_snapshot",
        lambda runtime, target: MeldSessionSnapshot(
            session=session,
            version_token="current-version",
        ),
    )
    client = MemCommitClient(
        root=tmp_path / "store",
        create=True,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("stale Meld response connected a provider")
        ),
    )

    with pytest.raises(MeldConflictError, match="changed"):
        client.comment_meld(
            "result",
            issue_uid="issue-1",
            option_uid="option-1",
            expected_version="reviewed-version",
        )


@pytest.mark.parametrize("method_name", ("preserve_meld", "defer_meld", "apply_meld"))
def test_saved_meld_mutations_reject_stale_reviews_before_execution(
    tmp_path,
    monkeypatch,
    method_name,
):
    session = _review_session()
    monkeypatch.setattr(
        meld_operation,
        "_meld_snapshot",
        lambda runtime, target: MeldSessionSnapshot(session, "current-version"),
    )
    for boundary in (
        "execute_meld_preservation",
        "execute_prepared_meld_turn",
        "execute_meld_session_defer",
        "execute_meld_apply",
    ):
        monkeypatch.setattr(
            meld_operation,
            boundary,
            lambda *args, _boundary=boundary, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"stale action crossed {_boundary}")
            ),
        )
    client = MemCommitClient(root=tmp_path / "store", create=True)

    with pytest.raises(MeldConflictError, match="changed"):
        getattr(client, method_name)(
            "result",
            expected_version="reviewed-version",
        )


def test_meld_current_context_failure_uses_the_meld_error_taxonomy():
    class BrokenStore:
        state_file = SimpleNamespace(exists=lambda: True)

        @staticmethod
        def current_context_name():
            raise ValueError("broken state pointer")

    with pytest.raises(MeldStorageError):
        meld_operation._current_context_name(SimpleNamespace(store=BrokenStore()))
