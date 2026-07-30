"""Compatibility boundary for Ground agreement without a completion field."""
from __future__ import annotations

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.ground import render_ground_snapshot
from memcommit.commands.ground_named_shell import (
    render_named_ground_goal_pane,
    render_named_ground_top_panel,
)
from memcommit.ground import GroundSession, create_ground_session
from memcommit.ground_turn_dialogue import ground_turn_aliases


runner = CliRunner()


def test_legacy_completion_round_trips_but_is_never_presented_or_inferred():
    legacy_text = "LEGACY COMPLETION MUST REMAIN OPAQUE"
    session = create_ground_session(
        "legacy-ground",
        goal="Agree on the current Goal, Rules, and Cases.",
        completion_criterion=legacy_text,
    )

    restored = GroundSession.from_dict(session.to_dict())
    _aliases, provider_payload = ground_turn_aliases(restored)

    assert restored.completion_criterion == legacy_text
    assert restored.to_dict()["completion_criterion"] == legacy_text
    assert legacy_text not in render_ground_snapshot(restored)
    assert legacy_text not in render_named_ground_top_panel(restored)
    assert legacy_text not in render_named_ground_goal_pane(restored)
    assert "completion" not in provider_payload


def test_removed_completion_option_cannot_create_hidden_ground_state(
    isolated_store,
):
    result = runner.invoke(
        app,
        [
            "ground",
            "hidden-completion",
            "--completion",
            "A hidden second Goal.",
        ],
    )

    assert result.exit_code != 0
    assert "No such option" in result.output
    assert not isolated_store.exists()
