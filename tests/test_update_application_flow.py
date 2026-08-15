"""Update's adapter for the shared review-to-Apply phase skeleton."""

from __future__ import annotations

from dataclasses import replace
from typing import cast
import uuid

import pytest

from memcommit.application_flow import run_application_flow
from memcommit.update import (
    GrantedUpdateTarget,
    UpdateApplicationReceipt,
    UpdateSession,
    operation_digest,
)
from memcommit.update_application_flow import (
    UpdateApplicationFlowError,
    UpdateApplicationFlowPort,
)


SHA256 = "0" * 64


def _staged() -> UpdateSession:
    return UpdateSession(
        uid=str(uuid.uuid4()),
        status="staged",
        created_at="2026-08-15T00:00:00+00:00",
        source_uid="source-uid",
        source_name="source",
        source_digest=SHA256,
        source_contexts=(),
        target_uid="target-uid",
        target_name="target",
        target_digest=SHA256,
        target_contexts=(),
        operations=(),
    )


def _applied(session: UpdateSession) -> UpdateSession:
    return session.with_application(
        UpdateApplicationReceipt(
            applied_at="2026-08-15T00:00:01+00:00",
            operation_digest=operation_digest(session.operations),
            target_digest=SHA256,
            target_contexts=(),
            checkpoints=(),
        )
    )


def _unexpected(*_args, **_kwargs):
    raise AssertionError("unexpected Update application phase")


@pytest.mark.parametrize(
    ("granted_source", "granted_target", "expected"),
    (
        (False, False, "local"),
        (True, False, "granted-source"),
        (False, True, "granted-target"),
        (True, True, "granted-target"),
    ),
)
def test_update_flow_dispatches_by_the_actual_mutation_owner(
    granted_source: bool,
    granted_target: bool,
    expected: str,
):
    session = _staged()
    marker = cast(GrantedUpdateTarget, object())
    session = replace(
        session,
        granted_source=marker if granted_source else None,
        granted_target=marker if granted_target else None,
    )
    calls: list[str] = []

    def apply(label: str, reviewed: UpdateSession) -> UpdateSession:
        calls.append(label)
        return _applied(reviewed)

    result = run_application_flow(
        session,
        port=UpdateApplicationFlowPort(
            interactive=False,
            reviewer=_unexpected,
            incorporate=_unexpected,
            local_applier=lambda reviewed: apply("local", reviewed),
            granted_source_applier=lambda reviewed: apply(
                "granted-source", reviewed
            ),
            granted_target_applier=lambda reviewed: apply(
                "granted-target", reviewed
            ),
        ),
    )

    assert result.status == "APPLIED"
    assert result.reviewed is session
    assert result.applied is not None and result.applied.status == "applied"
    assert calls == [expected]


def test_interactive_update_can_replace_the_reviewed_revision_before_apply():
    session = _staged()
    revised = replace(session, uid=str(uuid.uuid4()))
    observed: list[tuple[UpdateSession, str | None]] = []

    def review(prepared, incorporate, origin):
        observed.append((prepared, origin))
        return incorporate(prepared, "revise")

    port = UpdateApplicationFlowPort(
        interactive=True,
        reviewer=review,
        incorporate=lambda _current, guidance: revised
        if guidance == "revise"
        else _unexpected(),
        local_applier=_applied,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
        analysis_origin="EXACT_PREWARM",
    )

    result = run_application_flow(session, port=port)

    assert observed == [(session, "EXACT_PREWARM")]
    assert result.prepared is session
    assert result.reviewed is revised
    assert result.applied == _applied(revised)


def test_interactive_cancel_keeps_apply_unreachable():
    session = _staged()
    port = UpdateApplicationFlowPort(
        interactive=True,
        reviewer=lambda *_args: None,
        incorporate=_unexpected,
        local_applier=_unexpected,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
    )

    result = run_application_flow(session, port=port)

    assert result.status == "CANCELLED"
    assert result.applied is None


def test_update_flow_rejects_a_receipt_for_a_different_review():
    session = _staged()
    different = replace(session, target_name="other-target")
    port = UpdateApplicationFlowPort(
        interactive=False,
        reviewer=_unexpected,
        incorporate=_unexpected,
        local_applier=lambda _reviewed: _applied(different),
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
    )

    with pytest.raises(UpdateApplicationFlowError, match="outside the reviewed"):
        run_application_flow(session, port=port)


def test_update_flow_rejects_non_staged_input_and_review_output():
    session = _staged()
    port = UpdateApplicationFlowPort(
        interactive=True,
        reviewer=lambda *_args: replace(session, status="impact"),
        incorporate=_unexpected,
        local_applier=_unexpected,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
    )

    with pytest.raises(UpdateApplicationFlowError, match="invalid staged"):
        run_application_flow(session, port=port)
    with pytest.raises(UpdateApplicationFlowError, match="requires a staged"):
        run_application_flow(
            replace(session, status="impact"),
            port=replace(port, interactive=False),
        )
