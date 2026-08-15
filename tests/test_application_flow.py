"""Operation-neutral application phase orchestration contracts."""

from __future__ import annotations

import pytest

from memcommit.application_flow import ApplicationFlowResult, run_application_flow


class _Port:
    def __init__(self, *, reviewed="reviewed", applied="receipt") -> None:
        self.reviewed = reviewed
        self.applied = applied
        self.events: list[tuple[str, object]] = []

    def review(self, prepared):
        self.events.append(("review", prepared))
        return self.reviewed

    def apply(self, reviewed):
        self.events.append(("apply", reviewed))
        return self.applied


def test_application_flow_orders_review_before_apply_and_returns_typed_evidence():
    port = _Port()

    result = run_application_flow("prepared", port=port)

    assert result == ApplicationFlowResult(
        status="APPLIED",
        prepared="prepared",
        reviewed="reviewed",
        applied="receipt",
    )
    assert port.events == [("review", "prepared"), ("apply", "reviewed")]


def test_cancelled_review_never_reaches_apply():
    port = _Port(reviewed=None)

    result = run_application_flow("prepared", port=port)

    assert result.status == "CANCELLED"
    assert result.reviewed is None
    assert result.applied is None
    assert port.events == [("review", "prepared")]


def test_apply_failure_produces_no_applied_flow_result():
    class FailingPort(_Port):
        def apply(self, reviewed):
            super().apply(reviewed)
            raise RuntimeError("CAS failed")

    port = FailingPort()

    with pytest.raises(RuntimeError, match="CAS failed"):
        run_application_flow("prepared", port=port)

    assert port.events == [("review", "prepared"), ("apply", "reviewed")]


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
            reviewed="reviewed",
            applied=None,
        )
    with pytest.raises(ValueError, match="requires reviewed and applied"):
        ApplicationFlowResult(
            status="APPLIED",
            prepared="prepared",
            reviewed=None,
            applied=None,
        )
