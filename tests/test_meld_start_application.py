"""Terminal-independent construction contracts for Meld."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from memcommit.application.operations.meld.model import INLINE_MELD_CONTEXT_NAME, MELD_INLINE_MEMORY_SCHEMA_VERSION
from memcommit.application.operations.meld.start_application import (
    MeldStartError,
    MeldStartRequest,
    MeldStartResult,
    run_meld_start,
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

    def start(self, request, *, provider_factory):
        self.calls.append((request, provider_factory))
        return self.result


def test_start_request_enforces_directional_baseline_target():
    with pytest.raises(MeldStartError, match="BASELINE"):
        MeldStartRequest(
            mode="DIRECTIONAL",
            left_name="incoming",
            right_name="baseline",
            target_name="another",
        )


def test_start_request_rejects_memory_focus_outside_exact_directional_scope():
    with pytest.raises(MeldStartError, match="Only directional"):
        MeldStartRequest(
            mode="SYMMETRIC",
            left_name="left",
            right_name="right",
            target_name="result",
            incoming_memory="abc123",
        )

    with pytest.raises(MeldStartError, match="INCOMING.*descendants"):
        MeldStartRequest(
            mode="DIRECTIONAL",
            left_name="incoming",
            right_name="baseline",
            target_name="baseline",
            left_descendants=True,
            incoming_memory="abc123",
        )


def test_run_meld_start_rejects_a_port_that_drops_memory_focus():
    request = MeldStartRequest(
        mode="DIRECTIONAL",
        left_name="incoming",
        right_name="baseline",
        target_name="baseline",
        incoming_memory="abc123",
    )

    with pytest.raises(MeldStartError, match="outside"):
        run_meld_start(
            request,
            port=_Port(
                MeldStartResult(
                    session=_session(),
                    origin="PROVIDER",
                    created_target=False,
                )
            ),
            provider_factory=object(),
        )


def test_run_meld_start_validates_the_complete_port_result():
    request = MeldStartRequest(
        mode="DIRECTIONAL",
        left_name="incoming",
        right_name="baseline",
        target_name="baseline",
    )
    provider_factory = object()
    result = MeldStartResult(
        session=_session(),
        origin="PROVIDER",
        created_target=False,
    )
    port = _Port(result)

    assert run_meld_start(
        request,
        port=port,
        provider_factory=provider_factory,
    ) is result
    assert port.calls == [(request, provider_factory)]


def test_run_meld_start_rejects_a_port_that_changes_the_source_order():
    request = MeldStartRequest(
        mode="DIRECTIONAL",
        left_name="incoming",
        right_name="baseline",
        target_name="baseline",
    )
    port = _Port(
        MeldStartResult(
            session=_session(left="baseline", right="incoming"),
            origin="PROVIDER",
            created_target=False,
        )
    )

    with pytest.raises(MeldStartError, match="outside"):
        run_meld_start(request, port=port, provider_factory=object())


def test_inline_start_request_and_result_bind_the_exact_memory_content():
    content = 'all greetings need "."!'
    request = MeldStartRequest(
        mode="DIRECTIONAL",
        left_name=INLINE_MELD_CONTEXT_NAME,
        right_name="baseline",
        target_name="baseline",
        incoming_text=content,
    )
    session = SimpleNamespace(
        mode="DIRECTIONAL",
        schema_version=MELD_INLINE_MEMORY_SCHEMA_VERSION,
        frames=(
            SimpleNamespace(
                context_name=INLINE_MELD_CONTEXT_NAME,
                selected_memory_uid=None,
                memories=(SimpleNamespace(content="changed"),),
            ),
            SimpleNamespace(
                context_name="baseline",
                selected_memory_uid=None,
                memories=(),
            ),
        ),
        target=SimpleNamespace(context_name="baseline"),
        state="READY_TO_APPLY",
    )

    with pytest.raises(MeldStartError, match="outside"):
        run_meld_start(
            request,
            port=_Port(
                MeldStartResult(
                    session=session,
                    origin="PROVIDER",
                    created_target=False,
                )
            ),
            provider_factory=object(),
        )
