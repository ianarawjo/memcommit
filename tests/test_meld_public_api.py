"""Stable Python facade coverage for terminal-independent Meld."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import memcommit.api.client as client_module
from memcommit.api import (
    MeldContextError,
    MeldSessionResult,
    MemCommitClient,
)


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

    monkeypatch.setattr(client_module, "execute_meld_start", execute)
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

    monkeypatch.setattr(client_module, "execute_meld_restart", execute)
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
