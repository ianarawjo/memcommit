from __future__ import annotations

import memcommit.adapters.console.commands.meld.command as command
from memcommit.adapters.console.commands.meld.command import entrypoint
from memcommit.adapters.console.commands.meld.command import presentation
from memcommit.adapters.console.commands.meld.command import workflow
from memcommit.application.operations.meld.runtime import source_bindings


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


def test_meld_workflow_reuses_application_source_binding_implementation() -> None:
    assert workflow._load_bound_contexts is source_bindings.load_bound_meld_contexts
    assert workflow._load_meld_source is source_bindings.load_meld_source
    assert workflow._load_local_meld_source is source_bindings.load_local_meld_source
    assert workflow._bound_frame_digest is source_bindings.meld_bound_frame_digest
    assert (
        workflow._assert_source_bindings
        is source_bindings.assert_meld_source_bindings
    )
    assert (
        workflow._assert_non_target_source_bindings
        is source_bindings.assert_meld_non_target_source_bindings
    )
    assert (
        workflow._assert_unapplied_target
        is source_bindings.assert_unapplied_meld_target
    )
