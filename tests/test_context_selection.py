"""Shared Context selection and range-control contracts."""

import pytest

from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.context_targeting.loading import load_context_scope
from memcommit.context_targeting.tui.reach import (
    ContextReachState,
    render_context_reach,
)
from memcommit.context_targeting.tui.selection import ContextSelectionState


def test_legacy_context_scope_module_is_a_thin_compatibility_facade():
    from memcommit.context_scope import load_context_scope as legacy_loader

    assert legacy_loader is load_context_scope


def test_lexical_scope_expansion_deduplicates_overlapping_targets():
    scope = ContextScope.create(
        ("task", "task/child"),
        include_descendants=True,
    )

    assert expand_lexical_context_names(
        scope,
        ("other", "task/child", "task/child/deep", "task/peer"),
    ) == ("task", "task/child", "task/child/deep", "task/peer")


def test_context_scope_rejects_non_boolean_descendant_policy():
    with pytest.raises(ValueError, match="must be a boolean"):
        ContextScope.create(("task",), include_descendants=1)  # type: ignore[arg-type]


def test_multiple_selection_collapses_to_the_most_recent_explicit_target():
    state = ContextSelectionState.create(
        ("current", "peer", "third"),
        selected=("current",),
        mode="MULTIPLE",
    )

    assert state.choose("peer") is True
    assert state.selected_names == ("current", "peer")
    assert state.set_multiple(False) is True
    assert state.selected_names == ("peer",)
    assert state.mode == "SINGLE"


def test_multiple_selection_refuses_to_remove_its_last_target():
    state = ContextSelectionState.create(
        ("current", "peer"),
        selected=("current",),
        mode="MULTIPLE",
    )

    with pytest.raises(ValueError, match="at least 1 Context"):
        state.choose("current")


def test_context_reach_uses_one_shared_exact_and_descendant_vocabulary():
    state = ContextReachState.create(include_descendants=False)

    rendered = "".join(
        text
        for _style, text in render_context_reach(
            state,
            focused=True,
        )
    )

    assert "THIS CONTEXT ONLY" in rendered
    assert "INCLUDE DESCENDANTS" in rendered
    assert state.move(1) is True
    assert state.include_descendants is True
