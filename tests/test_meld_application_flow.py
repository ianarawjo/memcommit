"""Operation-neutral application-flow contracts specialized by Meld."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from memcommit.application_flow import run_application_flow
from memcommit.meld_application_flow import (
    MeldApplicationFlowError,
    MeldApplicationFlowPort,
)


def _reviewed_session():
    return SimpleNamespace(state="READY_TO_APPLY", application=None)


def test_meld_flow_hands_the_exact_review_and_digest_to_existing_apply():
    session = _reviewed_session()
    calls = []

    def apply(reviewed, expected_digest):
        calls.append((reviewed, expected_digest))
        reviewed.state = "APPLIED"
        reviewed.application = SimpleNamespace(
            checkpoint_uid="checkpoint-1",
            result_memory_uids=("memory-1", "memory-2"),
        )
        return False, "checkpoint-1", 2

    result = run_application_flow(
        session,
        port=MeldApplicationFlowPort(
            expected_session_digest="review-digest",
            applier=apply,
        ),
    )

    assert result.status == "APPLIED"
    assert calls == [(session, "review-digest")]
    assert result.applied == (False, "checkpoint-1", 2)


@pytest.mark.parametrize(
    "receipt, application",
    (
        ((False, "", 0), None),
        (
            (False, "another-checkpoint", 1),
            SimpleNamespace(
                checkpoint_uid="checkpoint-1",
                result_memory_uids=("memory-1",),
            ),
        ),
        (
            (False, "checkpoint-1", 2),
            SimpleNamespace(
                checkpoint_uid="checkpoint-1",
                result_memory_uids=("memory-1",),
            ),
        ),
    ),
)
def test_meld_flow_rejects_receipts_outside_the_applied_session(
    receipt,
    application,
):
    session = _reviewed_session()

    def apply(reviewed, _expected_digest):
        reviewed.state = "APPLIED"
        reviewed.application = application
        return receipt

    with pytest.raises(MeldApplicationFlowError):
        run_application_flow(
            session,
            port=MeldApplicationFlowPort(
                expected_session_digest="review-digest",
                applier=apply,
            ),
        )
