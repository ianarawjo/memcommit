"""Shared display-only suggestions for failed Context lookup."""

from __future__ import annotations

import pytest

from memcommit.application.context_locator import suggest_context_locators
from memcommit.core.context_targeting.checkpoint import (
    resolve_local_context_checkpoint_target,
)


class _CheckpointCatalog:
    def list_context_names(self) -> list[str]:
        return ["practice/rules", "practice/examples", "archive"]

    def list_checkpoints(self, name: str) -> list[dict]:
        return []


def test_context_suggestions_rank_canonical_names_without_resolving_them() -> None:
    assert suggest_context_locators(
        "pracitce/rules",
        current=None,
        available_names=("practice/examples", "practice/rules", "archive"),
    ) == ("practice/rules", "practice/examples")


def test_relative_context_suggestions_use_the_frozen_current_namespace() -> None:
    assert suggest_context_locators(
        "./rulse",
        current="practice",
        available_names=("practice/rules", "other/rules"),
    ) == ("practice/rules",)


def test_diff_failure_adds_context_suggestion_without_fuzzy_execution() -> None:
    store = _CheckpointCatalog()
    with pytest.raises(ValueError) as raised:
        resolve_local_context_checkpoint_target(
            store,
            "pracitce/rules",
            current=None,
        )

    assert str(raised.value) == (
        "Diff target 'pracitce/rules' is neither an existing Context nor an "
        "available checkpoint UID. Did you mean one of: 'practice/rules', "
        "'practice/examples'?"
    )
