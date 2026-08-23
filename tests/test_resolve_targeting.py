from __future__ import annotations

import pytest

import memcommit.ops as ops
from memcommit.context import Memory
from memcommit.resolve_application import ResolveError
from memcommit.resolve_targeting import normalize_resolve_cli_targets
from memcommit.store import MemoryStore


class _UnusedStore:
    def context_exists(self, _name: str) -> bool:
        raise AssertionError("Context-backed normalization must not scan the store.")

    def load_direct(self, _name: str):
        raise AssertionError("Context-backed normalization must not scan the store.")

    def load_direct_context_graph_strict(self):
        raise AssertionError("Context-backed normalization must not scan the store.")


def test_resolve_targets_classify_context_and_memory_auto_operands() -> None:
    targets = normalize_resolve_cli_targets(
        _UnusedStore(),
        ("practice/source", "abcdef12"),
        context_locator=None,
        memory_operands=(),
        current_context_name="practice",
    )

    assert targets.context_name == "practice/source"
    assert targets.memory_selectors == ("abcdef12",)


def test_resolve_targets_share_one_relative_context_snapshot() -> None:
    targets = normalize_resolve_cli_targets(
        _UnusedStore(),
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


def test_resolve_targets_reject_distinct_contexts() -> None:
    with pytest.raises(ResolveError, match="select multiple Contexts"):
        normalize_resolve_cli_targets(
            _UnusedStore(),
            ("work/source", "work/other:abcdef12"),
            context_locator=None,
            memory_operands=(),
            current_context_name="work/current",
        )
