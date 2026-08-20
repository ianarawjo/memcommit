"""Operation-neutral application phase orchestration contracts."""

from __future__ import annotations

import pytest

from memcommit.application_flow import ApplicationFlowResult, run_application_flow


class _Port:
    def __init__(self, *, decided="decided", applied="receipt") -> None:
        self.decided = decided
        self.applied = applied
        self.events: list[tuple[str, object]] = []

    def decide(self, prepared):
        self.events.append(("decide", prepared))
        return self.decided

    def apply(self, reviewed):
        self.events.append(("apply", reviewed))
        return self.applied


def test_application_flow_orders_decision_before_apply_and_returns_typed_evidence():
    port = _Port()

    result = run_application_flow("prepared", port=port)

    assert result == ApplicationFlowResult(
        status="APPLIED",
        prepared="prepared",
        decided="decided",
        applied="receipt",
    )
    assert port.events == [("decide", "prepared"), ("apply", "decided")]


def test_cancelled_decision_never_reaches_apply():
    port = _Port(decided=None)

    result = run_application_flow("prepared", port=port)

    assert result.status == "CANCELLED"
    assert result.decided is None
    assert result.applied is None
    assert port.events == [("decide", "prepared")]


def test_apply_failure_produces_no_applied_flow_result():
    class FailingPort(_Port):
        def apply(self, reviewed):
            super().apply(reviewed)
            raise RuntimeError("CAS failed")

    port = FailingPort()

    with pytest.raises(RuntimeError, match="CAS failed"):
        run_application_flow("prepared", port=port)

    assert port.events == [("decide", "prepared"), ("apply", "decided")]


def test_flow_rejects_missing_prepared_or_applied_values():
    with pytest.raises(TypeError, match="prepared value"):
        run_application_flow(None, port=_Port())
    with pytest.raises(TypeError, match="no applied receipt"):
        run_application_flow("prepared", port=_Port(applied=None))


def test_flow_result_rejects_impossible_phase_combinations():
    with pytest.raises(ValueError, match="cancelled application"):
        ApplicationFlowResult(
            status="CANCELLED",
            prepared="prepared",
            decided="decided",
            applied=None,
        )
    with pytest.raises(ValueError, match="requires decided and applied"):
        ApplicationFlowResult(
            status="APPLIED",
            prepared="prepared",
            decided=None,
            applied=None,
        )
