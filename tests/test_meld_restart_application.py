"""Terminal-independent replacement contracts for Meld."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from memcommit.application.operations.meld.restart_application import (
    MeldRestartError,
    MeldRestartRequest,
    MeldRestartResult,
    run_meld_restart,
)


def _session(*, mode="DIRECTIONAL", left="incoming", right="baseline"):
    return SimpleNamespace(
        mode=mode,
        frames=(
            SimpleNamespace(context_name=left),
            SimpleNamespace(context_name=right),
        ),
        target=SimpleNamespace(
            context_name=right if mode == "DIRECTIONAL" else "result"
        ),
        state="AWAITING_REPLY",
    )


class _Port:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def restart(self, request, *, provider_factory):
        self.calls.append((request, provider_factory))
        return self.result


def test_restart_requires_an_opaque_saved_version():
    with pytest.raises(MeldRestartError, match="opaque saved version"):
        MeldRestartRequest(
            mode="DIRECTIONAL",
            left_name="incoming",
            right_name="baseline",
            target_name="baseline",
            expected_version="",
        )


def test_restart_rejects_memory_focus_with_recursive_baseline():
    with pytest.raises(MeldRestartError, match="BASELINE.*descendants"):
        MeldRestartRequest(
            mode="DIRECTIONAL",
            left_name="incoming",
            right_name="baseline",
            target_name="baseline",
            expected_version="version-1",
            right_descendants=True,
            baseline_memory="def456",
        )


def test_run_meld_restart_validates_the_complete_port_result():
    request = MeldRestartRequest(
        mode="DIRECTIONAL",
        left_name="incoming",
        right_name="baseline",
        target_name="baseline",
        expected_version="version-1",
    )
    provider_factory = object()
    result = MeldRestartResult(session=_session(), origin="PROVIDER")
    port = _Port(result)

    assert run_meld_restart(
        request,
        port=port,
        provider_factory=provider_factory,
    ) is result
    assert port.calls == [(request, provider_factory)]


def test_run_meld_restart_rejects_a_port_that_changes_the_source_order():
    request = MeldRestartRequest(
        mode="DIRECTIONAL",
        left_name="incoming",
        right_name="baseline",
        target_name="baseline",
        expected_version="version-1",
    )
    port = _Port(
        MeldRestartResult(
            session=_session(left="baseline", right="incoming"),
            origin="PROVIDER",
        )
    )

    with pytest.raises(MeldRestartError, match="outside"):
        run_meld_restart(request, port=port, provider_factory=object())
