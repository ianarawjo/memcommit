"""Existing Context identity resolution preserves access and UID semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from memcommit.application.capabilities.operand_resolution import (
    ContextOperandAmbiguityError,
    ContextOperandNotFoundError,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_context_access_or_inline_text,
    resolve_existing_context_access,
    try_resolve_context_access_or_local_memory,
)
from memcommit.core.context import Context, Memory
from memcommit.core.context_targeting.model import DirectMemoryTarget, InlineTextOperand
from memcommit.persistence.store import MemoryStore


def _store(tmp_path: Path) -> MemoryStore:
    store = MemoryStore(root=tmp_path / "store")
    store.save(
        Context(
            uid="2a4dc8ab-cc03-5721-923f-03e3b4669cf5",
            name="practice/coffee/a",
        )
    )
    store.save(
        Context(
            uid="aaaaaaaa-1111-4111-8111-111111111111",
            name="practice/coffee/b",
        )
    )
    return store


def test_access_resolution_returns_the_same_binding_for_name_and_uid(tmp_path: Path):
    store = _store(tmp_path)
    candidates = freeze_profile_context_access_candidates(
        store,
        current_name="practice/coffee/b",
    )

    by_name = resolve_existing_context_access(
        store,
        "practice/coffee/a",
        current_name="practice/coffee/b",
        candidates=candidates,
    )
    by_uid = resolve_existing_context_access(
        store,
        "2a4dc8ab",
        current_name="practice/coffee/b",
        candidates=candidates,
    )

    assert by_uid.uid == by_name.uid
    assert by_uid.name == by_name.name
    assert by_uid.value.context_name == "practice/coffee/a"


def test_uid_never_falls_through_to_inline_text(tmp_path: Path):
    store = _store(tmp_path)

    with pytest.raises(ContextOperandNotFoundError, match="UID 'deadbeef'"):
        resolve_context_access_or_inline_text(
            store,
            "deadbeef",
            current_name="practice/coffee/b",
        )


def test_nonportable_prose_remains_available_to_explicitly_overloaded_grammar(
    tmp_path: Path,
):
    store = _store(tmp_path)

    resolved = resolve_context_access_or_inline_text(
        store,
        "make every final word a fruit",
        current_name="practice/coffee/b",
    )

    assert resolved == InlineTextOperand("make every final word a fruit")


def test_access_memory_grammar_resolves_both_kinds_from_one_uid_frame(
    tmp_path: Path,
):
    store = _store(tmp_path)
    owner = store.load_direct("practice/coffee/b")
    memory = Memory(
        uid="52b75243-1111-4111-8111-111111111111",
        content="owned value",
    )
    owner.add(memory)
    store.save(owner)
    candidates = freeze_profile_context_access_candidates(
        store,
        current_name=owner.name,
    )

    context = try_resolve_context_access_or_local_memory(
        store,
        "2a4dc8ab",
        current_name=owner.name,
        candidates=candidates,
    )
    selected_memory = try_resolve_context_access_or_local_memory(
        store,
        "52b75243",
        current_name=owner.name,
        candidates=candidates,
    )

    assert context is not None and context.name == "practice/coffee/a"
    assert selected_memory == DirectMemoryTarget(owner.name, memory.uid)


def test_access_memory_grammar_rejects_cross_kind_uid_ambiguity(tmp_path: Path):
    store = _store(tmp_path)
    owner = store.load_direct("practice/coffee/b")
    owner.add(
        Memory(
            uid="2a4dc8ab-2222-4222-8222-222222222222",
            content="colliding Memory",
        )
    )
    store.save(owner)

    with pytest.raises(ContextOperandAmbiguityError, match="matches 2"):
        try_resolve_context_access_or_local_memory(
            store,
            "2a4dc8ab",
            current_name=owner.name,
        )
