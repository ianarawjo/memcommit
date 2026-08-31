"""Typed Context operand resolution composes names, UID, and text safely."""

from __future__ import annotations

import pytest

from memcommit.application.capabilities.operand_resolution import (
    ContextOperandAmbiguityError,
    ContextOperandCandidate,
    ContextOperandNotFoundError,
    resolve_context_or_inline_text_operand,
    resolve_existing_context_operand,
    try_resolve_existing_context_operand,
)
from memcommit.core.context_targeting.model import ContextTarget, InlineTextOperand


def _candidate(uid: str, name: str) -> ContextOperandCandidate[ContextTarget]:
    return ContextOperandCandidate(uid=uid, name=name, value=ContextTarget(name))


CONTEXTS = (
    _candidate(
        "2a4dc8ab-cc03-5721-923f-03e3b4669cf5",
        "practice/coffee/compare-merge-meld-update/a",
    ),
    _candidate(
        "aaaaaaaa-1111-4111-8111-111111111111",
        "practice/coffee/other",
    ),
)


def test_context_name_and_relative_locator_win_before_uid_resolution() -> None:
    by_name = resolve_existing_context_operand(
        CONTEXTS,
        "practice/coffee/other",
        current="practice/coffee/current",
    )
    relative = resolve_existing_context_operand(
        CONTEXTS,
        "../other",
        current="practice/coffee/current",
    )

    assert by_name.name == "practice/coffee/other"
    assert relative.uid == by_name.uid


def test_context_uid_prefix_resolves_inside_the_frozen_catalog() -> None:
    resolved = resolve_existing_context_operand(
        CONTEXTS,
        "2a4dc8ab",
        current="practice/coffee/current",
    )

    assert resolved.uid == "2a4dc8ab-cc03-5721-923f-03e3b4669cf5"
    assert resolved.value == ContextTarget(
        "practice/coffee/compare-merge-meld-update/a"
    )


def test_missing_uid_fails_closed_instead_of_becoming_inline_text() -> None:
    with pytest.raises(ContextOperandNotFoundError, match="UID 'deadbeef'"):
        resolve_context_or_inline_text_operand(
            CONTEXTS,
            "deadbeef",
            current="practice/coffee/current",
        )


def test_context_or_text_uses_prose_only_after_name_and_uid_routes() -> None:
    context = resolve_context_or_inline_text_operand(
        CONTEXTS,
        "2a4dc8ab",
        current="practice/coffee/current",
    )
    prose = resolve_context_or_inline_text_operand(
        CONTEXTS,
        "make every final word a fruit",
        current="practice/coffee/current",
    )

    assert context == resolve_existing_context_operand(
        CONTEXTS,
        "2a4dc8ab",
        current="practice/coffee/current",
    )
    assert prose == InlineTextOperand("make every final word a fruit")


def test_missing_portable_name_remains_a_context_error() -> None:
    assert (
        try_resolve_existing_context_operand(
            CONTEXTS,
            "practice/coffee/typo",
            current="practice/coffee/current",
        )
        is None
    )
    with pytest.raises(ContextOperandNotFoundError, match="typo"):
        resolve_context_or_inline_text_operand(
            CONTEXTS,
            "practice/coffee/typo",
            current="practice/coffee/current",
        )


def test_same_uid_through_multiple_public_routes_requires_an_exact_name() -> None:
    candidates = (
        _candidate(
            "bbbbbbbb-1111-4111-8111-111111111111",
            "shared/one",
        ),
        _candidate(
            "bbbbbbbb-1111-4111-8111-111111111111",
            "alias/one",
        ),
    )

    with pytest.raises(ContextOperandAmbiguityError, match="multiple public routes"):
        resolve_existing_context_operand(
            candidates,
            "bbbbbbbb",
            current=None,
        )
