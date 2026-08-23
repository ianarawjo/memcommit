"""Flagless Forget setup and command-entry contracts."""

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.forget_runtime as forget_runtime
from memcommit.cli import app
from memcommit.commands import forget as forget_command
from memcommit.commands.forget_setup_workbench import (
    ForgetSetupReceipt,
    choose_forget_setup,
)
from memcommit.semantic.changes import RemoveChange
from memcommit.store import MemoryStore


runner = CliRunner()


def test_forget_provider_follows_the_active_profile_route(monkeypatch):
    provider = object()
    operations: list[str] = []
    monkeypatch.setattr(
        forget_runtime,
        "connect_operation_provider",
        lambda operation: operations.append(operation) or (provider, object()),
    )

    assert forget_command.connect_codex_chatgpt_provider() is provider
    assert operations == ["forget"]


def test_forget_setup_enter_runs_the_current_direct_source():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Forget the old desk location.\r")
        receipt = choose_forget_setup(
            ("alpha", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == ForgetSetupReceipt(
        context_name="alpha",
        instruction="Forget the old desk location.",
    )


def test_forget_setup_selects_one_peer_source_before_todo():
    with create_pipe_input() as pipe_input:
        # Enter an instruction, move to Source, check beta, then run from To Do.
        pipe_input.send_text("Forget the old desk location.\t\x1b[B\r\t\r")
        receipt = choose_forget_setup(
            ("alpha", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == ForgetSetupReceipt(
        context_name="beta",
        instruction="Forget the old desk location.",
    )


def test_forget_setup_keeps_backspace_as_instruction_deletion():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Forget the old desk locationx\x7f.\r")
        receipt = choose_forget_setup(
            ("alpha",),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt == ForgetSetupReceipt(
        context_name="alpha",
        instruction="Forget the old desk location.",
    )


def test_forget_setup_rejects_blank_submission_then_escape_cancels():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r\x1b")
        receipt = choose_forget_setup(
            ("alpha",),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is None


def _store_with_two_contexts() -> tuple[MemoryStore, str, str]:
    store = MemoryStore()
    current = ops.init("forget/current")
    selected = ops.init("forget/selected")
    ops.add(current, "Keep the current Context unchanged.")
    ops.add(selected, "The desk was previously beside the west entrance.")
    store.create_context(current)
    store.create_context(selected)
    store.set_current(current.name)
    return store, current.name, selected.name


def test_flagless_forget_uses_the_frozen_selected_context(
    isolated_store,
    monkeypatch,
):
    _store, current_name, selected_name = _store_with_two_contexts()
    observed: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(forget_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        forget_command,
        "choose_forget_setup",
        lambda names, *, current, annotations: (
            ForgetSetupReceipt(selected_name, "Forget the old desk location.")
        ),
    )
    monkeypatch.setattr(
        forget_command,
        "connect_codex_chatgpt_provider",
        lambda: object(),
    )
    monkeypatch.setattr(
        forget_command,
        "_run_interactive_forget",
        lambda ctx, info, _provider, **kwargs: observed.append(
            (ctx.name, info, kwargs["mutates_granted_authority"])
        )
        or [],
    )

    result = runner.invoke(app, ["forget"])

    assert result.exit_code == 0, result.output + result.stderr
    assert current_name != selected_name
    assert observed == [
        (selected_name, "Forget the old desk location.", False)
    ]


def test_flagless_forget_cancel_does_not_connect_provider(
    isolated_store,
    monkeypatch,
):
    _store_with_two_contexts()
    monkeypatch.setattr(forget_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        forget_command,
        "choose_forget_setup",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        forget_command,
        "connect_codex_chatgpt_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider connected")),
    )

    result = runner.invoke(app, ["forget"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "Forget cancelled." in result.output


def test_flagless_forget_requires_an_instruction_outside_a_terminal(
    isolated_store,
    monkeypatch,
):
    monkeypatch.setattr(forget_command, "_interactive_terminal", lambda: False)

    result = runner.invoke(app, ["forget"])

    assert result.exit_code == 1
    assert "INSTRUCTION is required outside a terminal" in result.output


def test_explicit_forget_instruction_keeps_the_existing_fast_path(
    isolated_store,
    monkeypatch,
):
    _store, current_name, _selected_name = _store_with_two_contexts()
    observed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        forget_command,
        "choose_forget_setup",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("setup opened")
        ),
    )
    monkeypatch.setattr(
        forget_command,
        "connect_codex_chatgpt_provider",
        lambda: object(),
    )
    monkeypatch.setattr(
        forget_command,
        "_run_interactive_forget",
        lambda ctx, info, _provider, **_kwargs: observed.append((ctx.name, info)) or [],
    )

    result = runner.invoke(app, ["forget", "Forget the old desk location."])

    assert result.exit_code == 0, result.output + result.stderr
    assert observed == [(current_name, "Forget the old desk location.")]


def test_tty_forget_prints_a_receipt_only_after_the_checkpoint_succeeds(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("forget/receipt")
    memory = ops.add(context, "The desk was previously beside the west entrance.")
    store.create_context(context)
    store.set_current(context.name)

    def approve_remove(ctx, _info, _provider, **_kwargs):
        change = RemoveChange(
            uid=memory.uid,
            content=memory.content,
            reason="The reviewed instruction covers this Memory.",
        )
        return [change]

    monkeypatch.setattr(forget_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        forget_command,
        "connect_codex_chatgpt_provider",
        lambda: object(),
    )
    monkeypatch.setattr(
        forget_command,
        "_run_interactive_forget",
        approve_remove,
    )

    result = runner.invoke(app, ["forget", "Forget the old desk location."])

    assert result.exit_code == 0, result.output + result.stderr
    assert "FORGET APPLIED · SOURCE forget/receipt" in result.output
    assert "EFFECTS · REMOVE 1 · EDIT 0" in result.output
    assert "REVIEW · mem review forget --receipt" in result.output
    assert "RECOVERY · mem undo" in result.output
    assert memory.uid not in store.load_direct(context.name).memories
