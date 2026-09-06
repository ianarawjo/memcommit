"""Stable Python facade coverage for terminal-independent Meld."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import memcommit.adapters.python_api._operations.meld as meld_operation
from memcommit.adapters.python_api import (
    MeldConflictError,
    MeldContextError,
    MeldDecisionInput,
    MeldSessionResult,
    MeldStorageError,
    MemCommitClient,
)
from memcommit.application.operations.meld.session import MeldSessionVersionError


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
        return SimpleNamespace(session=session, origin="PROVIDER")

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

    assert result.origin == "PROVIDER"
    assert calls[0][0].expected_version == "saved-version"
    assert calls[0][0].mode == "DIRECTIONAL"


def test_open_meld_maps_missing_target_to_public_context_error(tmp_path):
    client = MemCommitClient(root=tmp_path / "store", create=True)

    with pytest.raises(MeldContextError):
        client.open_meld("missing")


def test_resolve_meld_delegates_the_complete_decision_set(
    tmp_path,
    monkeypatch,
):
    client = MemCommitClient(root=tmp_path / "store", create=True)
    calls = []

    monkeypatch.setattr(
        meld_operation,
        "resolve_meld",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or "resolved"),
    )
    decisions = (
        MeldDecisionInput("issue-1", "confirm"),
        MeldDecisionInput("issue-2", "force"),
    )

    assert (
        client.resolve_meld(
            "result",
            decisions,
            expected_version="saved-version",
        )
        == "resolved"
    )
    assert calls == [
        (
            (client._runtime, "result", decisions),
            {"expected_version": "saved-version"},
        )
    ]


def test_resolve_meld_rejects_a_stale_review_before_provider_connection(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        meld_operation,
        "_expected_meld_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            MeldSessionVersionError(
                "The saved Meld changed after this action was reviewed."
            )
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
        client.resolve_meld(
            "result",
            (),
            expected_version="reviewed-version",
        )


def test_retired_meld_lifecycle_methods_are_not_public(tmp_path):
    client = MemCommitClient(root=tmp_path / "store", create=True)

    assert not hasattr(client, "comment_meld")
    assert not hasattr(client, "preserve_meld")
    assert not hasattr(client, "defer_meld")
    assert not hasattr(client, "apply_meld")


def test_meld_current_context_failure_uses_the_meld_error_taxonomy():
    class BrokenStore:
        state_file = SimpleNamespace(exists=lambda: True)

        @staticmethod
        def current_context_name():
            raise ValueError("broken state pointer")

    with pytest.raises(MeldStorageError):
        meld_operation._current_context_name(SimpleNamespace(store=BrokenStore()))
