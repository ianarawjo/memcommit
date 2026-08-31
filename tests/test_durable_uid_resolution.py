"""Shared durable UID resolution stays bounded to caller-supplied evidence."""

from __future__ import annotations

import pytest

from memcommit.application.capabilities.durable_uid_resolution import (
    DurableUidAmbiguityError,
    DurableUidCandidate,
    try_resolve_durable_uid,
)


def _candidate(uid: str, value: str) -> DurableUidCandidate[str]:
    return DurableUidCandidate(uid=uid, kind="memory", value=value)


def test_exact_uid_returns_every_occurrence_of_one_durable_identity():
    uid = "11111111-1111-4111-8111-111111111111"

    result = try_resolve_durable_uid(
        (_candidate(uid, "direct"), _candidate(uid, "reference occurrence")),
        uid,
    )

    assert result is not None
    assert result.uid == uid
    assert result.values == ("direct", "reference occurrence")


def test_unique_public_prefix_resolves_but_ambiguous_prefix_fails_closed():
    candidates = (
        _candidate("aaaaaaaa-1111-4111-8111-111111111111", "one"),
        _candidate("aaaaaaaa-2222-4222-8222-222222222222", "two"),
    )

    with pytest.raises(DurableUidAmbiguityError, match="2 readable identities"):
        try_resolve_durable_uid(candidates, "aaaaaaaa")

    resolved = try_resolve_durable_uid(candidates, "aaaaaaaa-1")
    assert resolved is not None
    assert resolved.values == ("one",)


def test_unknown_or_short_nonexact_text_is_not_reclassified_as_a_uid():
    candidates = (_candidate("aaaaaaaa-1111-4111-8111-111111111111", "one"),)

    assert try_resolve_durable_uid(candidates, "ordinary search") is None
    assert try_resolve_durable_uid(candidates, "aaaa") is None


def test_non_uuid_artifact_uid_uses_the_same_printed_eight_character_prefix():
    uid = "rationale:11111111-1111-4111-8111-111111111111"

    result = try_resolve_durable_uid(
        (_candidate(uid, "rationale artifact"),),
        uid[:8],
    )

    assert result is not None
    assert result.uid == uid
    assert result.values == ("rationale artifact",)
