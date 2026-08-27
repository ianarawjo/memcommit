"""Compact Goal authoring without invalidating older Ground records."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.ground.model import (
    GROUND_GOAL_WORD_LIMIT,
    GroundError,
    GroundSession,
    create_ground_session,
)


runner = CliRunner()


def _words(count: int) -> str:
    return " ".join(f"word{index}" for index in range(count))


def test_new_goal_accepts_forty_words_and_rejects_forty_one():
    accepted = create_ground_session(
        "forty-word-goal",
        goal=_words(GROUND_GOAL_WORD_LIMIT),
    )

    assert len(accepted.goal.split()) == GROUND_GOAL_WORD_LIMIT
    with pytest.raises(GroundError, match="40 words or fewer"):
        create_ground_session(
            "too-long-goal",
            goal=_words(GROUND_GOAL_WORD_LIMIT + 1),
        )


def test_legacy_long_goal_still_round_trips_until_it_is_revised():
    payload = create_ground_session("legacy-long-goal").to_dict()
    payload["goal"] = _words(GROUND_GOAL_WORD_LIMIT + 1)

    restored = GroundSession.from_dict(payload)

    assert restored.goal == payload["goal"]
    assert restored.to_dict()["goal"] == payload["goal"]


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
