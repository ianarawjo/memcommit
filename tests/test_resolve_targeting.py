from __future__ import annotations

import pytest

from memcommit.resolve_application import ResolveError
from memcommit.resolve_targeting import normalize_resolve_cli_targets


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


def test_resolve_targets_accept_short_prefix_only_as_explicit_memory() -> None:
    positional = normalize_resolve_cli_targets(
        _UnusedStore(),
        ("abcd",),
        context_locator=None,
        memory_operands=(),
        current_context_name="work/current",
    )
    explicit = normalize_resolve_cli_targets(
        _UnusedStore(),
        (),
        context_locator="work/current",
        memory_operands=("abcd",),
        current_context_name="work/current",
    )

    assert positional.context_name == "abcd"
    assert positional.memory_selectors == ()
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
