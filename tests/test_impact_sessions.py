"""Standalone Impact routes for saved operation artifacts."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.commands.impact as impact_command
import memcommit.commands.update as update_command
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.help_inventory import COMMAND_FORMS
from memcommit.commands.impact_sessions import (
    render_impact_session_snapshot,
    update_impact_presentation,
)
from memcommit.store import MemoryStore
from memcommit.update import plan_update


runner = CliRunner(mix_stderr=False)


class _UpdateProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": payload["target"]["memories"][0]["target_id"],
                        "new_content": "The verified route is now south.",
                        "source_ids": [
                            payload["source"]["memories"][0]["source_id"]
                        ],
                        "reason": "Verified evidence supersedes the old route.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


def test_help_names_every_supported_impact_operation():
    result = runner.invoke(app, ["impact", "--help"])

    assert result.exit_code == 0, result.output
    for operation in ("atomize", "meld", "sever", "update"):
        assert operation in result.output
    assert any(form.startswith("mem impact meld") for form in COMMAND_FORMS["impact"])
    assert any(
        form.startswith("mem impact update") for form in COMMAND_FORMS["impact"]
    )


@pytest.mark.parametrize(
    ("operation", "runner_name"),
    (
        ("meld", "_saved_meld_impact"),
        ("sever", "_saved_sever_impact"),
        ("update", "_saved_update_impact"),
    ),
)
def test_saved_operation_routes_dispatch_without_planning(
    isolated_store,
    monkeypatch,
    operation,
    runner_name,
):
    observed = []

    def open_saved(_store, *, session_uid):
        observed.append(session_uid)

    monkeypatch.setattr(impact_command, runner_name, open_saved)

    result = runner.invoke(
        app,
        ["impact", operation, "--session", "artifact-1"],
    )

    assert result.exit_code == 0, result.output
    assert observed == ["artifact-1"]


def test_saved_operation_route_rejects_planning_options(isolated_store, monkeypatch):
    monkeypatch.setattr(
        impact_command,
        "_saved_meld_impact",
        lambda *_args, **_kwargs: pytest.fail("invalid form reached the loader"),
    )

    result = runner.invoke(app, ["impact", "meld", "--to", "target"])

    assert result.exit_code == 2
    assert "opens a saved session" in result.stderr


def test_saved_update_impact_renders_exact_diff_with_apply_handoff():
    source = ops.init("source")
    ops.add(source, "The verified route is now south.")
    target = ops.init("target")
    ops.add(target, "The route is north.")
    session = plan_update(source, target, lambda: _UpdateProvider())

    rendered = render_impact_session_snapshot(
        update_impact_presentation(session)
    )

    assert "IMPACT · UPDATE" in rendered
    assert "- The route is north." in rendered
    assert "+ The verified route is now south." in rendered
    assert "[ APPLY? ]" in rendered
    assert "does not apply anything yet" in rendered
    assert "REVIEW & APPLY" not in rendered
    assert "MATERIALIZE" not in rendered
    assert "INCORPORATE RESPONSES" not in rendered
    assert "APPLY CHANGES" not in rendered


def test_cli_reopens_saved_update_impact_without_provider(
    isolated_store,
    monkeypatch,
):
    source = ops.init("source")
    ops.add(source, "The verified route is now south.")
    target = ops.init("target")
    ops.add(target, "The route is north.")
    session = plan_update(source, target, lambda: _UpdateProvider())
    MemoryStore().save_impact_plan(session)
    monkeypatch.setattr(
        impact_command,
        "connect_codex_chatgpt_provider",
        lambda: pytest.fail("saved Impact inspection called a provider"),
    )

    result = runner.invoke(app, ["impact", "update"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "IMPACT · UPDATE" in result.output
    assert "- The route is north." in result.output
    assert "+ The verified route is now south." in result.output
    assert "[ APPLY? ]" in result.output
    assert "REVIEW & APPLY" not in result.output
    assert "APPLY CHANGES" not in result.output


def test_saved_update_apply_handoff_reenters_owning_update_flow(
    isolated_store,
    monkeypatch,
):
    source = ops.init("source")
    ops.add(source, "The verified route is now south.")
    target = ops.init("target")
    ops.add(target, "The route is north.")
    session = plan_update(source, target, lambda: _UpdateProvider())
    store = MemoryStore()
    store.save_impact_plan(session)
    observed = []

    monkeypatch.setattr(
        impact_command,
        "_show_saved_impact",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        update_command,
        "cmd",
        lambda **kwargs: observed.append(kwargs),
    )

    impact_command._saved_update_impact(store, session_uid=session.uid)

    assert observed == [
        {
            "source_name": "source",
            "target_name": "target",
            "replace_stage": False,
            "source_descendants": False,
            "target_descendants": False,
        }
    ]
