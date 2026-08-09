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
from memcommit.context_targeting.tui.tree import (
    build_context_tree,
    context_subtree_names,
)


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


def test_multiple_selection_allows_an_empty_staged_set():
    state = ContextSelectionState.create(
        ("current", "peer"),
        selected=("current",),
        mode="MULTIPLE",
    )

    assert state.choose("current") is True
    assert state.selected_names == ()


def test_empty_multiple_selection_uses_visible_fallback_when_switching_to_single():
    state = ContextSelectionState.create(
        ("current", "peer"),
        selected=(),
        mode="MULTIPLE",
    )

    assert state.set_multiple(False, fallback_name="peer") is True
    assert state.selected_name == "peer"
    assert state.mode == "SINGLE"


def test_empty_multiple_selection_requires_a_valid_single_fallback():
    state = ContextSelectionState.create(
        ("current", "peer"),
        selected=(),
        mode="MULTIPLE",
    )

    with pytest.raises(ValueError, match="requires a visible fallback"):
        state.set_multiple(False)

    assert state.mode == "MULTIPLE"
    assert state.selected_names == ()


def test_multiple_selection_group_toggle_checks_and_clears_a_whole_subtree():
    catalog = ("task", "task/a", "task/a/deep", "task/b", "other")
    tree = build_context_tree(catalog)
    state = ContextSelectionState.create(
        catalog,
        selected=("other",),
        mode="MULTIPLE",
    )
    subtree = context_subtree_names(tree, "task")

    assert subtree == ("task", "task/a", "task/a/deep", "task/b")
    assert state.toggle_group(subtree, anchor_name="task") is True
    assert state.selected_names == catalog
    assert state.most_recent_name == "task"

    # Acting on a checked parent excludes its complete subtree, even if one
    # descendant had already been changed independently.
    assert state.choose("task/a") is True
    assert state.toggle_group(subtree, anchor_name="task") is True
    assert state.selected_names == ("other",)


def test_group_toggle_on_unchecked_parent_restores_a_partial_subtree():
    catalog = ("task", "task/a", "task/b")
    tree = build_context_tree(catalog)
    state = ContextSelectionState.create(
        catalog,
        selected=("task/a",),
        mode="MULTIPLE",
    )

    assert state.toggle_group(
        context_subtree_names(tree, "task"),
        anchor_name="task",
    ) is True
    assert state.selected_names == catalog
    assert state.set_multiple(False) is True
    assert state.selected_names == ("task",)


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
