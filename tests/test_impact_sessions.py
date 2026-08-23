"""Standalone Impact routes for saved operation artifacts."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from typer.testing import CliRunner

import memcommit.commands.impact as impact_command
import memcommit.commands.update as update_command
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.help_inventory import COMMAND_FORMS
from memcommit.commands.impact_registry import IMPACT_ROUTES, ImpactLifecycle
from memcommit.commands.impact_sessions import (
    render_impact_session_snapshot,
    update_impact_presentation,
)
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionOpenReceipt,
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
    for operation in IMPACT_ROUTES.names:
        assert operation in result.output
    assert "--sessions" in result.output
    assert IMPACT_ROUTES.route("forget").lifecycle is ImpactLifecycle.PREPARE_PROCESS_LOCAL
    assert IMPACT_ROUTES.route("distill").lifecycle is ImpactLifecycle.PREPARE_PROCESS_LOCAL
    assert IMPACT_ROUTES.route("resolve").lifecycle is ImpactLifecycle.PREPARE_PROCESS_LOCAL
    assert IMPACT_ROUTES.route("update").lifecycle is ImpactLifecycle.PREPARE_OR_OPEN
    assert {route.name for route in IMPACT_ROUTES.deferred} == {"dedun"}
    assert {operation.name for operation in IMPACT_ROUTES.excluded} == {
        "ground",
        "translate",
    }
    assert any(
        form.startswith('mem impact forget "[instruction]"')
        for form in COMMAND_FORMS["impact"]
    )
    assert any(
        form.startswith("mem impact distill") for form in COMMAND_FORMS["impact"]
    )
    assert any(
        form.startswith("mem impact resolve") for form in COMMAND_FORMS["impact"]
    )
    assert any(form.startswith("mem impact meld") for form in COMMAND_FORMS["impact"])
    assert any(
        form.startswith("mem impact update") for form in COMMAND_FORMS["impact"]
    )
    assert any(
        form.startswith("mem impact --sessions") for form in COMMAND_FORMS["impact"]
    )
    assert any(
        form.startswith("mem impact atomize --session")
        for form in COMMAND_FORMS["impact"]
    )


def test_aggregate_sessions_dispatches_selected_artifact_exactly(
    isolated_store,
    monkeypatch,
):
    receipt = SessionOpenReceipt(
        kind="sever",
        key="sever-session",
        argv=("mem", "impact", "sever", "--session", "sever-session"),
    )
    monkeypatch.setattr(
        impact_command,
        "choose_impact_session",
        lambda _store, *, kinds, title: receipt,
    )
    observed = []
    monkeypatch.setattr(
        impact_command,
        "_operation_session_impact",
        lambda **kwargs: observed.append(kwargs),
    )

    result = runner.invoke(app, ["impact", "--sessions"])

    assert result.exit_code == 0, result.output + result.stderr
    assert observed == [
        {
            "operation": impact_command.ImpactOperation.sever,
            "session_uid": "sever-session",
            "show_all": False,
        }
    ]


def test_atomize_sessions_filters_catalog_and_dispatches_exact_analysis(
    isolated_store,
    monkeypatch,
):
    receipt = SessionOpenReceipt(
        kind="atomize",
        key="atomize-analysis",
        argv=(
            "mem",
            "impact",
            "atomize",
            "--session",
            "atomize-analysis",
        ),
    )
    observed_catalog = []
    monkeypatch.setattr(
        impact_command,
        "choose_impact_session",
        lambda _store, *, kinds, title: (
            observed_catalog.append((kinds, title)) or receipt
        ),
    )
    observed_open = []
    monkeypatch.setattr(
        impact_command,
        "_operation_session_impact",
        lambda **kwargs: observed_open.append(kwargs),
    )

    result = runner.invoke(app, ["impact", "atomize", "--sessions", "--all"])

    assert result.exit_code == 0, result.output + result.stderr
    assert observed_catalog == [(("atomize",), "MEM IMPACT · ATOMIZE ANALYSES")]
    assert observed_open == [
        {
            "operation": impact_command.ImpactOperation.atomize,
            "session_uid": "atomize-analysis",
            "show_all": True,
        }
    ]


def test_atomize_exact_session_dispatches_without_context_resolution(
    isolated_store,
    monkeypatch,
):
    observed = []
    monkeypatch.setattr(
        impact_command,
        "_saved_atomize_impact",
        lambda _store, *, session_uid, show_all: observed.append(
            (session_uid, show_all)
        ),
    )

    result = runner.invoke(
        app,
        ["impact", "atomize", "--session", "analysis-1"],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert observed == [("analysis-1", False)]


def test_atomize_saved_selection_rejects_new_analysis_inputs(isolated_store):
    result = runner.invoke(
        app,
        ["impact", "atomize", "source", "--sessions"],
    )

    assert result.exit_code == 2
    assert "cannot be combined" in result.stderr


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
    assert "No such option" in result.stderr
    assert "--to" in result.stderr


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
    impact_views = iter((True, False))

    monkeypatch.setattr(
        impact_command,
        "_show_saved_impact",
        lambda *_args, **_kwargs: next(impact_views),
    )
    monkeypatch.setattr(
        update_command,
        "cmd",
        lambda **kwargs: observed.append(kwargs),
    )

    impact_command._saved_update_impact(store, session_uid=session.uid[:8])

    assert observed == [
        {
            "source_name": "source",
            "target_name": "target",
            "replace_stage": False,
            "source_descendants": False,
            "target_descendants": False,
        }
    ]


def test_terminal_owning_apply_does_not_reopen_impact(monkeypatch):
    source = ops.init("source")
    ops.add(source, "The verified route is now south.")
    target = ops.init("target")
    ops.add(target, "The route is north.")
    current = {"value": update_impact_presentation(
        plan_update(source, target, lambda: _UpdateProvider())
    )}
    shown = []

    monkeypatch.setattr(
        impact_command,
        "_show_saved_impact",
        lambda presentation, *, kind: shown.append((presentation, kind)) or True,
    )

    def finish_apply():
        current["value"] = replace(
            current["value"],
            handoff_available=False,
        )

    impact_command._run_saved_impact_handoff_loop(
        load_presentation=lambda: current["value"],
        open_owning_workflow=finish_apply,
        kind="update",
    )

    assert len(shown) == 1
