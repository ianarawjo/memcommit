"""Compact Goal authoring for physical Ground workspaces."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.ground_workbench.ground.contracts import (
    GROUND_GOAL_WORD_LIMIT,
    GroundError,
    validate_ground_goal,
)


runner = CliRunner()


def _words(count: int) -> str:
    return " ".join(f"word{index}" for index in range(count))


def test_new_goal_accepts_forty_words_and_rejects_forty_one():
    accepted = validate_ground_goal(_words(GROUND_GOAL_WORD_LIMIT))

    assert len(accepted.split()) == GROUND_GOAL_WORD_LIMIT
    with pytest.raises(GroundError, match="40 words or fewer"):
        validate_ground_goal(_words(GROUND_GOAL_WORD_LIMIT + 1))


def test_cli_rejects_long_goal_before_creating_a_ground(isolated_store):
    result = runner.invoke(
        app,
        [
            "ground",
            "too-long-goal",
            "--goal",
            _words(GROUND_GOAL_WORD_LIMIT + 1),
        ],
    )

    assert result.exit_code == 1
    assert "40 words or fewer" in result.output
    assert not isolated_store.exists()
