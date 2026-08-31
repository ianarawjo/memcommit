from __future__ import annotations

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.core.context import Memory
from memcommit.application.operations.resolve.application import ResolveError
from memcommit.application.operations.resolve.targeting import normalize_resolve_cli_targets
from memcommit.persistence.store import MemoryStore


def test_resolve_targets_classify_context_and_memory_auto_operands(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("practice/source")
    memory = Memory(
        uid="abcdef12-1111-4111-8111-111111111111",
        content="focused",
    )
    source.add(memory)
    store.save(source)
    store.save(ops.init("practice"))
    targets = normalize_resolve_cli_targets(
        store,
        ("practice/source", "abcdef12"),
        context_locator=None,
        memory_operands=(),
        current_context_name="practice",
    )

    assert targets.context_name == "practice/source"
    assert targets.memory_selectors == (memory.uid,)


def test_resolve_targets_share_one_relative_context_snapshot(isolated_store) -> None:
    store = MemoryStore()
    source = ops.init("work/source")
    source.add(
        Memory(
            uid="abcdef12-1111-4111-8111-111111111111",
            content="focused",
        )
    )
    store.save(source)
    store.save(ops.init("work/current"))
    targets = normalize_resolve_cli_targets(
        store,
        ("../source:abcdef12",),
        context_locator="work/source",
        memory_operands=(),
        current_context_name="work/current",
    )

    assert targets.context_name == "work/source"
    assert targets.memory_selectors == ("abcdef12",)


def test_resolve_targets_accept_short_prefix_as_auto_or_explicit_memory(
    isolated_store,
) -> None:
    store = MemoryStore()
    owner = ops.init("work/owner")
    memory = Memory(
        uid="abcd1111-1111-4111-8111-111111111111",
        content="short prefix target",
    )
    owner.add(memory)
    current = ops.init("work/current")
    store.save(owner)
    store.save(current)
    positional = normalize_resolve_cli_targets(
        store,
        ("abcd",),
        context_locator=None,
        memory_operands=(),
        current_context_name="work/current",
    )
    explicit = normalize_resolve_cli_targets(
        store,
        (),
        context_locator="work/current",
        memory_operands=("abcd",),
        current_context_name="work/current",
    )

    assert positional.context_name == owner.name
    assert positional.memory_selectors == (memory.uid,)
    assert explicit.context_name == "work/current"
    assert explicit.memory_selectors == ("abcd",)


def test_resolve_targets_accept_context_uid_as_context_not_memory(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("work/source")
    store.save(source)

    targets = normalize_resolve_cli_targets(
        store,
        (source.uid[:8],),
        context_locator=None,
        memory_operands=(),
        current_context_name=None,
    )

    assert targets.context_name == source.name
    assert targets.memory_selectors == ()


def test_resolve_targets_reject_distinct_contexts(isolated_store) -> None:
    store = MemoryStore()
    store.save(ops.init("work/source"))
    other = ops.init("work/other")
    other.add(
        Memory(
            uid="abcdef12-1111-4111-8111-111111111111",
            content="focused",
        )
    )
    store.save(other)
    store.save(ops.init("work/current"))
    with pytest.raises(ResolveError, match="select multiple Contexts"):
        normalize_resolve_cli_targets(
            store,
            ("work/source", "work/other:abcdef12"),
            context_locator=None,
            memory_operands=(),
            current_context_name="work/current",
        )
