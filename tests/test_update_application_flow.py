"""Update's adapter for the shared review-to-Apply phase skeleton."""

from __future__ import annotations

from dataclasses import replace
from typing import cast
import uuid

import pytest

from memcommit.application.capabilities.flow import run_application_flow
from memcommit.application.operations.update.model import (
    EditOperation,
    GrantedUpdateTarget,
    UpdateApplicationReceipt,
    UpdateSession,
    operation_digest,
)
from memcommit.application.operations.update.execution import (
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


def _grant_marker() -> GrantedUpdateTarget:
    return cast(GrantedUpdateTarget, object())


def _mutation_staged() -> UpdateSession:
    return replace(
        _staged(),
        operations=(
            EditOperation(
                owner_context_uid="target-uid",
                owner_context_name="target",
                memory_uid="memory-uid",
                old_content="old",
                new_content="new",
                source_refs=(),
                reason="test mutation",
            ),
        ),
    )


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
            local_applier=lambda reviewed: apply("local", reviewed),
            granted_source_applier=lambda reviewed: apply("granted-source", reviewed),
            granted_target_applier=lambda reviewed: apply("granted-target", reviewed),
            authority_reviewer=lambda reviewed: reviewed,
        ),
    )

    assert result.status == "APPLIED"
    assert result.decided is session
    assert result.applied is not None and result.applied.status == "applied"
    assert calls == [expected]


def test_update_flow_has_no_intermediate_decision_or_cancel_phase():
    session = _staged()
    port = UpdateApplicationFlowPort(
        local_applier=_applied,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
    )

    result = run_application_flow(session, port=port)

    assert result.status == "APPLIED"
    assert result.prepared is session
    assert result.decided is session
    assert result.applied == _applied(session)


def test_direct_application_decider_runs_for_a_local_mutation():
    session = _mutation_staged()
    reviewed = []
    port = UpdateApplicationFlowPort(
        local_applier=_applied,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
        application_decider=lambda current: reviewed.append(current) or current,
    )

    result = run_application_flow(session, port=port)

    assert reviewed == [session]
    assert result.status == "APPLIED"


def test_direct_application_decider_also_owns_a_zero_operation_receipt():
    session = _staged()
    decided = []
    port = UpdateApplicationFlowPort(
        local_applier=_applied,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
        application_decider=lambda current: decided.append(current) or current,
    )

    result = run_application_flow(session, port=port)

    assert decided == [session]
    assert result.status == "APPLIED"


def test_direct_application_decision_cannot_replace_the_semantic_plan():
    session = _mutation_staged()
    revised = replace(
        session,
        uid=str(uuid.uuid4()),
        created_at="2026-08-15T00:00:02+00:00",
        operations=(),
    )
    port = UpdateApplicationFlowPort(
        local_applier=_applied,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
        application_decider=lambda _current: revised,
    )

    with pytest.raises(UpdateApplicationFlowError, match="exact prepared proposal"):
        run_application_flow(session, port=port)


def test_direct_application_decision_cannot_change_the_target_boundary():
    session = _mutation_staged()
    port = UpdateApplicationFlowPort(
        local_applier=_unexpected,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
        application_decider=lambda current: replace(
            current,
            target_name="different",
        ),
    )

    with pytest.raises(UpdateApplicationFlowError, match="exact prepared proposal"):
        run_application_flow(session, port=port)


def test_granted_target_keeps_only_exact_authority_approval():
    marker = _grant_marker()
    session = replace(_mutation_staged(), granted_target=marker)
    reviewed = []
    port = UpdateApplicationFlowPort(
        local_applier=_unexpected,
        granted_source_applier=_unexpected,
        granted_target_applier=_applied,
        authority_reviewer=lambda current: reviewed.append(current) or current,
    )

    result = run_application_flow(session, port=port)

    assert reviewed == [session]
    assert result.status == "APPLIED"


def test_granted_target_authority_review_cannot_replace_the_plan():
    session = replace(_mutation_staged(), granted_target=_grant_marker())
    port = UpdateApplicationFlowPort(
        local_applier=_unexpected,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
        authority_reviewer=lambda current: replace(current, uid=str(uuid.uuid4())),
    )

    with pytest.raises(UpdateApplicationFlowError, match="different staged plan"):
        run_application_flow(session, port=port)


def test_update_flow_rejects_a_receipt_for_a_different_review():
    session = _staged()
    different = replace(session, target_name="other-target")
    port = UpdateApplicationFlowPort(
        local_applier=lambda _reviewed: _applied(different),
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
    )

    with pytest.raises(UpdateApplicationFlowError, match="outside the decided"):
        run_application_flow(session, port=port)


def test_update_flow_rejects_non_staged_input():
    session = _staged()
    port = UpdateApplicationFlowPort(
        local_applier=_unexpected,
        granted_source_applier=_unexpected,
        granted_target_applier=_unexpected,
    )

    with pytest.raises(UpdateApplicationFlowError, match="requires a staged"):
        run_application_flow(
            replace(session, status="impact"),
            port=port,
        )
