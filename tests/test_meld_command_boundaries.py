from __future__ import annotations

import memcommit.adapters.console.commands.meld.command as command
from memcommit.adapters.console.commands.meld.command import entrypoint
from memcommit.adapters.console.commands.meld.command import presentation
from memcommit.adapters.console.commands.meld.command import workflow


def test_meld_command_facade_preserves_existing_imports() -> None:
    assert command.cmd is entrypoint.cmd
    assert command.render_meld_session is presentation.render_meld_session
    assert (
        command.start_reviewed_symmetric_meld is workflow.start_reviewed_symmetric_meld
    )
    assert command._resume_picked_meld is workflow._resume_picked_meld


def test_meld_entrypoint_delegates_one_validated_request(monkeypatch) -> None:
    store = object()
    calls = []

    monkeypatch.setattr(entrypoint, "MemoryStore", lambda *, create: store)
    monkeypatch.setattr(
        entrypoint,
        "execute_meld_command",
        lambda **kwargs: calls.append(kwargs),
    )

    entrypoint.cmd(left="incoming", right="baseline")

    assert len(calls) == 1
    assert calls[0]["store"] is store
    request = calls[0]["request"]
    assert isinstance(request, workflow.MeldCommandRequest)
    assert request.left == "incoming"
    assert request.right == "baseline"
    assert request.to_is_symmetric is False
    assert request.directional_to is None
    assert request.left_descendants is False
    assert request.right_descendants is False


def test_meld_command_compatibility_assignment_reaches_owning_module(
    monkeypatch,
) -> None:
    def replacement():
        return object()

    monkeypatch.setattr(command, "connect_codex_chatgpt_provider", replacement)

    assert workflow.connect_codex_chatgpt_provider is replacement
    assert not hasattr(entrypoint, "connect_codex_chatgpt_provider")


def test_meld_workflow_has_no_direct_typer_output_dependency() -> None:
    assert not hasattr(workflow, "typer")
