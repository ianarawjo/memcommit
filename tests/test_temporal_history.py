"""Shared direct-Memory delta contracts for Log and Trace."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from memcommit.temporal_history import direct_memory_deltas


@dataclass(frozen=True)
class _State:
    content: str


def test_uid_stable_delta_extraction_is_shared_without_inventing_lineage():
    before = {"m1": _State("old"), "removed": _State("gone")}
    after = {"m1": _State("new"), "created": _State("fresh")}

    deltas = direct_memory_deltas(
        before,
        after,
        before_order=("m1", "removed"),
        after_order=("m1", "created"),
        content=lambda state: state.content,
    )

    assert [
        (delta.kind, delta.memory_uid)
        for delta in deltas
    ] == [
        ("EDITED", "m1"),
        ("REMOVED", "removed"),
        ("CREATED", "created"),
    ]
    assert deltas[1].after is None
    assert deltas[2].before is None


def test_frame_order_must_cover_exactly_the_direct_memory_catalog():
    with pytest.raises(ValueError, match="order"):
        direct_memory_deltas(
            {"m1": _State("one")},
            {},
            before_order=(),
            after_order=(),
            content=lambda state: state.content,
        )
