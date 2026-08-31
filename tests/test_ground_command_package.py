"""Physical Ground command package ownership contracts."""

from __future__ import annotations

import inspect

from memcommit.adapters.console.commands.ground_workbench.ground.command import entrypoint, workflow


def test_ground_command_entrypoint_delegates_one_typed_request(monkeypatch) -> None:
    captured: list[workflow.GroundCommandRequest] = []
    monkeypatch.setattr(entrypoint, "run_ground_command", captured.append)

    entrypoint.cmd()

    assert captured == [workflow.GroundCommandRequest()]
    assert len(inspect.signature(entrypoint.cmd).parameters) == 12


def test_ground_workflow_helpers_have_responsibility_named_owners() -> None:
    expected_owners = {
        workflow.GroundCommandRequest: "workflow.command",
        workflow._run_new_ground_shell: "workflow.create",
        workflow._run_named_ground_workspace: "workflow.edit",
        workflow._run_ground_session_picker: "workflow.open",
        workflow.render_ground_start: "workflow.inspect",
        workflow._run_approved_ground_command: "workflow.apply",
    }

    for value, suffix in expected_owners.items():
        assert value.__module__.endswith(suffix)
