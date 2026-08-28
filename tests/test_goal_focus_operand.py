"""Shared Context, Memory, and inline Goal-focus projection."""

from __future__ import annotations

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.semantic.goal_focus import GoalFocusError
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    freeze_goal_focus_context,
    freeze_goal_focus_operand,
    revalidate_goal_focus,
)
from memcommit.persistence.store import MemoryStore


def test_goal_operand_freezes_context_memory_and_inline_with_one_contract(
    isolated_store,
) -> None:
    store = MemoryStore()
    goals = ops.init("coffee/goals")
    first = ops.add(goals, "Help a friend's cafe improve repeat visits.")
    ops.add(goals, "Keep recommendations feasible for a small team.")
    store.save(goals)

    context_focus = freeze_goal_focus_operand(
        store,
        goals.name,
        current_name=None,
    )
    memory_focus = freeze_goal_focus_operand(
        store,
        f"{goals.name}:{first.uid[:8]}",
        current_name=None,
    )
    inline_focus = freeze_goal_focus_operand(
        store,
        "Give practical advice to a friend who owns a cafe.",
        current_name=None,
    )

    assert context_focus.kind == "CONTEXT"
    assert [item.memory_uid for item in context_focus.items] == list(goals.order)
    assert "[g000001]" in context_focus.text
    assert memory_focus.kind == "MEMORY"
    assert memory_focus.text == first.content
    assert inline_focus.kind == "INLINE"
    assert inline_focus.items[0].memory_uid is None


def test_goal_operand_fails_closed_for_locator_typos_and_missing_memory(
    isolated_store,
) -> None:
    store = MemoryStore()

    with pytest.raises(GoalFocusError, match="does not exist"):
        freeze_goal_focus_operand(
            store,
            "coffee/goasl",
            current_name=None,
        )
    with pytest.raises(Exception, match="No directly owned Memory"):
        freeze_goal_focus_operand(
            store,
            "deadbeef",
            current_name=None,
        )

    forced = freeze_goal_focus_operand(
        store,
        "text:coffee/goasl",
        current_name=None,
    )
    assert forced.text == "coffee/goasl"


def test_goal_focus_revalidation_binds_the_complete_context_preimage(
    isolated_store,
) -> None:
    store = MemoryStore()
    goals = ops.init("ground/goals")
    ops.add(goals, "Keep the advice practical.")
    store.save(goals)
    frozen = freeze_goal_focus_operand(store, goals.name, current_name=None)

    ops.add(goals, "Prefer reversible experiments.")
    store.save(goals)

    with pytest.raises(GoalFocusError, match="changed"):
        revalidate_goal_focus(store, frozen)


def test_ground_goal_lane_is_an_ordinary_memory_focus_with_adapter_cardinality() -> None:
    context = ops.init("ground/goals")
    ops.add(context, "One reviewed top-level Goal.")

    focus = freeze_goal_focus_context(
        context,
        kind="GROUND",
        require_single=True,
    )

    assert focus.kind == "GROUND"
    assert focus.items[0].context_name == "ground/goals"

    context.add("Another Goal.")
    with pytest.raises(GoalFocusError, match="exactly one"):
        freeze_goal_focus_context(
            context,
            kind="GROUND",
            require_single=True,
        )
