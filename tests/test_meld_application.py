"""Terminal-independent routing contracts for reviewed Meld Apply."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from memcommit.meld import MELD_OWNER_AWARE_SCHEMA_VERSION
from memcommit.meld_application import (
    MeldApplicationError,
    MeldApplyReceipt,
    MeldApplyRequest,
    meld_apply_route,
    run_meld_apply,
)


def _session(
    *,
    mode="SYMMETRIC",
    schema_version=3,
    granted_target=None,
):
    return SimpleNamespace(
        mode=mode,
        schema_version=schema_version,
        granted_target=granted_target,
        state="READY_TO_APPLY",
        application=None,
    )


@pytest.mark.parametrize(
    "session, expected",
    (
        (_session(), "STANDARD_TARGET"),
        (_session(mode="DIRECTIONAL"), "STANDARD_TARGET"),
        (
            _session(
                mode="DIRECTIONAL",
                schema_version=MELD_OWNER_AWARE_SCHEMA_VERSION,
            ),
            "LOCAL_OWNER_SUBTREE",
        ),
        (
            _session(mode="DIRECTIONAL", granted_target=object()),
            "GRANTED_TARGET",
        ),
        (
            _session(
                mode="DIRECTIONAL",
                schema_version=MELD_OWNER_AWARE_SCHEMA_VERSION,
                granted_target=object(),
            ),
            "GRANTED_OWNER_SUBTREE",
        ),
    ),
)
def test_meld_apply_route_preserves_each_authority_and_storage_shape(
    session,
    expected,
):
    assert meld_apply_route(session) == expected


class _Port:
    def __init__(self, *, mismatch=False):
        self.calls = []
        self.mismatch = mismatch

    def _apply(self, route, session, expected_session_digest):
        self.calls.append((route, session, expected_session_digest))
        session.state = "APPLIED"
        session.application = SimpleNamespace(
            checkpoint_uid="different" if self.mismatch else "checkpoint-1",
            result_memory_uids=("memory-1",),
        )
        return MeldApplyReceipt(False, "checkpoint-1", 1)

    def apply_standard_target(self, session, *, expected_session_digest):
        return self._apply("STANDARD_TARGET", session, expected_session_digest)

    def apply_local_owner_subtree(self, session, *, expected_session_digest):
        return self._apply("LOCAL_OWNER_SUBTREE", session, expected_session_digest)

    def apply_granted_target(self, session, *, expected_session_digest):
        return self._apply("GRANTED_TARGET", session, expected_session_digest)

    def apply_granted_owner_subtree(self, session, *, expected_session_digest):
        return self._apply("GRANTED_OWNER_SUBTREE", session, expected_session_digest)


@pytest.mark.parametrize(
    "session, expected_route",
    (
        (_session(), "STANDARD_TARGET"),
        (
            _session(
                mode="DIRECTIONAL",
                schema_version=MELD_OWNER_AWARE_SCHEMA_VERSION,
            ),
            "LOCAL_OWNER_SUBTREE",
        ),
        (
            _session(mode="DIRECTIONAL", granted_target=object()),
            "GRANTED_TARGET",
        ),
        (
            _session(
                mode="DIRECTIONAL",
                schema_version=MELD_OWNER_AWARE_SCHEMA_VERSION,
                granted_target=object(),
            ),
            "GRANTED_OWNER_SUBTREE",
        ),
    ),
)
def test_run_meld_apply_routes_exact_review_and_validates_receipt(
    session,
    expected_route,
):
    port = _Port()
    result = run_meld_apply(
        MeldApplyRequest(session=session, expected_session_digest="digest-1"),
        port=port,
    )

    assert result.session is session
    assert result.route == expected_route
    assert result.receipt == MeldApplyReceipt(False, "checkpoint-1", 1)
    assert port.calls == [(expected_route, session, "digest-1")]


def test_run_meld_apply_rejects_a_receipt_outside_the_applied_session():
    with pytest.raises(MeldApplicationError, match="outside the reviewed"):
        run_meld_apply(
            MeldApplyRequest(
                session=_session(),
                expected_session_digest="digest-1",
            ),
            port=_Port(mismatch=True),
        )
