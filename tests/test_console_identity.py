from __future__ import annotations

import pytest

from memcommit.adapters.console.identity import collision_safe_uid_prefixes


def test_compact_uid_projection_uses_eight_characters_when_unique() -> None:
    first = "b925d6bf-aec7-4de5-a432-7cf627d72628"
    second = "c10409ad-52f7-4e1f-b834-9a5dc1b48e71"

    assert collision_safe_uid_prefixes((first, second)) == {
        first: "b925d6bf",
        second: "c10409ad",
    }


def test_compact_uid_projection_expands_only_colliding_prefixes() -> None:
    first = "deadbeef-1111-1111-1111-111111111111"
    second = "deadbeef-2222-2222-2222-222222222222"
    third = "cafebabe-3333-3333-3333-333333333333"

    assert collision_safe_uid_prefixes((first, second, third)) == {
        first: "deadbeef-1",
        second: "deadbeef-2",
        third: "cafebabe",
    }


def test_compact_uid_projection_rejects_nonpositive_width() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        collision_safe_uid_prefixes(("memory-uid",), minimum_width=0)
