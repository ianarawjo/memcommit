"""Shared Context selection and range-control contracts."""

import pytest

from memcommit.context_targeting.model import ContextScope, DirectMemoryTarget
from memcommit.context_targeting.resolution import (
    expand_lexical_context_names,
    order_context_names_by_hierarchy,
)
from memcommit.context_targeting.loading import load_context_scope
from memcommit.context_targeting.tui.reach import (
    ContextReachState,
    ContextReachViewState,
    render_context_reach,
)
from memcommit.context_targeting.tui.range_selection import (
    ContextRangeSelectionState,
    project_checked_context_names,
)
from memcommit.context_targeting.tui.selection import ContextSelectionState
from memcommit.context_targeting.tui.memory_selection import (
    DirectMemorySelectionState,
)
from memcommit.context_targeting.tui.tree import (
    build_context_tree,
    context_subtree_names,
    visible_context_rows,
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


def test_public_catalog_order_matches_a_fully_expanded_context_tree():
    catalog = (
        "practice",
        "task-1",
        "task-1/description",
        "task-2",
        "task-1/campus-wiki",
        "task-1/campus-wiki/public",
        "external",
    )
    ordered = order_context_names_by_hierarchy(catalog)
    tree = build_context_tree(catalog)

    assert ordered == (
        "practice",
        "task-1",
        "task-1/description",
        "task-1/campus-wiki",
        "task-1/campus-wiki/public",
        "task-2",
        "external",
    )
    assert tuple(
        row.name for row in visible_context_rows(tree, tree.expandable_names)
    ) == ordered


def test_context_scope_rejects_non_boolean_descendant_policy():
    with pytest.raises(ValueError, match="must be a boolean"):
        ContextScope.create(("task",), include_descendants=1)  # type: ignore[arg-type]


def test_direct_memory_selection_keeps_exact_owner_separate_from_hover():
    target = DirectMemoryTarget("task/source", "memory-uid")
    state = DirectMemorySelectionState()

    assert state.choose(target) is True
    assert state.choose(target) is False
    assert state.selected == target
    assert state.clear_unless_context("task/source") is False
    assert state.clear_unless_context("task/other") is True
    assert state.selected is None


def test_multiple_direct_memory_selection_toggles_exact_owner_uid_pairs():
    first = DirectMemoryTarget("task/source", "first-memory")
    second = DirectMemoryTarget("task/other", "second-memory")
    state = DirectMemorySelectionState(mode="MULTIPLE")

    assert state.choose(first) is True
    assert state.choose(second) is True
    assert state.selected_targets == (first, second)
    assert state.choose(first) is True
    assert state.selected_targets == (second,)
    assert state.clear_unless_context("task/source") is False


def test_multiple_direct_memory_selection_retains_explicit_batch_order():
    first = DirectMemoryTarget("task/source", "first-memory")
    second = DirectMemoryTarget("task/source", "second-memory")
    state = DirectMemorySelectionState(mode="MULTIPLE")

    state.choose(second)
    state.choose(first)

    assert state.selected_targets == (second, first)


def test_multiple_direct_memory_selection_has_no_ambiguous_single_value():
    state = DirectMemorySelectionState(
        mode="MULTIPLE",
        selected_targets=(DirectMemoryTarget("task/source", "memory-uid"),),
    )

    with pytest.raises(ValueError, match="has no single target"):
        _ = state.selected


@pytest.mark.parametrize(
    ("context_name", "memory_uid"),
    (("", "memory-uid"), ("task/source", "")),
)
def test_direct_memory_target_requires_both_exact_identity_parts(
    context_name,
    memory_uid,
):
    with pytest.raises(ValueError, match="Context name and exact uid"):
        DirectMemoryTarget(context_name, memory_uid)


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


def test_selection_can_replace_a_computed_group_without_leaking_cardinality():
    state = ContextSelectionState.create(
        ("one", "two", "three"),
        selected=("one",),
        mode="MULTIPLE",
    )

    assert state.replace(("two", "three")) is True
    assert state.selected_names == ("two", "three")
    assert state.replace(("two", "three")) is False

    state.set_multiple(False)
    with pytest.raises(ValueError, match="exactly one"):
        state.replace(())


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

    assert (
        state.toggle_group(
            context_subtree_names(tree, "task"),
            anchor_name="task",
        )
        is True
    )
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


def test_context_reach_view_offers_both_before_individual_scopes():
    state = ContextReachViewState.create(mode="BOTH")

    rendered = "".join(
        text for _style, text in render_context_reach(state, focused=True)
    )

    assert rendered.index("BOTH") < rendered.index("THIS CONTEXT ONLY")
    assert rendered.index("THIS CONTEXT ONLY") < rendered.index("INCLUDE DESCENDANTS")
    assert state.mode == "BOTH"
    assert state.move(1) is True
    assert state.mode == "EXACT"
    assert state.move(1) is True
    assert state.mode == "SUBTREE"


def test_checked_context_projection_shows_effective_reachable_rows_only():
    tree = build_context_tree(("task", "task/readable", "task/query-only", "other"))

    assert project_checked_context_names(
        tree,
        ("task",),
        include_descendants=False,
    ) == ("task",)
    assert project_checked_context_names(
        tree,
        ("task",),
        include_descendants=True,
        selectable_names=frozenset({"task", "task/readable", "other"}),
    ) == ("task", "task/readable")


def test_context_range_freezes_effective_descendants_without_hidden_reexpansion():
    state = ContextRangeSelectionState.create(
        ("task", "task/a", "task/a/deep", "task/b", "other"),
        current_name="task",
        initial_target="task",
        multiple=True,
        include_descendants=True,
    )

    assert state.effective_names == (
        "task",
        "task/a",
        "task/a/deep",
        "task/b",
    )

    state.tree.selected_name = "task/a"
    assert state.toggle_cursor() is True
    assert state.effective_names == ("task", "task/b")

    # A checked parent clears its complete subtree even when a child was
    # changed independently. Toggling the now-unchecked parent restores the
    # whole subtree visibly and in the exact executable set.
    state.tree.selected_name = "task"
    assert state.toggle_cursor() is True
    assert state.effective_names == ()
    assert state.toggle_cursor() is True
    assert state.effective_names == (
        "task",
        "task/a",
        "task/a/deep",
        "task/b",
    )


def test_context_range_profile_is_process_local_and_can_be_cleared_while_editing():
    state = ContextRangeSelectionState.create(
        ("task", "task/a", "other"),
        current_name="task",
        initial_target="task",
        multiple=True,
        include_descendants=False,
    )

    state.profile_cursor = True
    assert state.toggle_cursor() is True
    assert state.profile_selected is True
    assert state.effective_names == state.catalog

    assert state.toggle_cursor() is True
    assert state.profile_selected is False
    assert state.effective_names == ()


def test_context_range_can_present_a_local_all_scope_without_changing_mechanics():
    state = ContextRangeSelectionState.create(
        ("task", "other"),
        current_name="task",
        initial_target="task",
        multiple=True,
        include_descendants=False,
    )

    rendered = "".join(
        text
        for _style, text in state.render_rows(
            focused=False,
            profile_label="ALL",
            profile_description="ALL LOCAL CONTEXTS",
        )
    )

    assert "ALL  ALL LOCAL CONTEXTS" in rendered
    assert state.effective_names == ("task",)
