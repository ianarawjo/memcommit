"""Contracts for interactive Context selection in ``mem switch``."""
from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.context_picker import choose_context
from memcommit.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_switch_help_documents_namespace_parent_navigation():
    result = invoke("switch", "--help")

    assert result.exit_code == 0
    assert "use '..' for an existing" in result.output
    assert "namespace parent" in result.output


def test_picker_preselects_current_and_accepts_enter():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = choose_context(
            ("alpha", "beta", "gamma"),
            current="beta",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "beta"


def test_picker_moves_with_arrows_and_clamps_at_boundaries():
    with create_pipe_input() as pipe_input:
        # beta -> gamma -> beta -> alpha -> clamp at alpha -> accept
        pipe_input.send_text("\x1b[B\x1b[A\x1b[A\x1b[A\r")
        selected = choose_context(
            ("alpha", "beta", "gamma"),
            current="beta",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == "alpha"


def test_picker_cancels_without_a_selection():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        selected = choose_context(
            ("alpha", "beta"),
            current="alpha",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_bare_switch_uses_picker_result(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")
    observed: dict[str, object] = {}

    def select(names, *, current):
        observed["names"] = names
        observed["current"] = current
        return "alpha"

    monkeypatch.setattr(
        "memcommit.commands.switch.choose_context",
        select,
    )

    result = invoke("switch")

    assert result.exit_code == 0
    assert "Switched to context 'alpha'" in result.output
    assert observed == {
        "names": ["alpha", "beta"],
        "current": "beta",
    }
    assert MemoryStore().current_context_name() == "alpha"


def test_bare_switch_cancel_preserves_current(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")
    monkeypatch.setattr(
        "memcommit.commands.switch.choose_context",
        lambda names, *, current: None,
    )

    result = invoke("switch")

    assert result.exit_code == 0
    assert "Switch cancelled" in result.output
    assert MemoryStore().current_context_name() == "beta"


def test_picker_result_is_revalidated_before_switch(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")

    def delete_selected_then_return_it(names, *, current):
        MemoryStore().delete("alpha")
        return "alpha"

    monkeypatch.setattr(
        "memcommit.commands.switch.choose_context",
        delete_selected_then_return_it,
    )

    result = invoke("switch")

    assert result.exit_code == 1
    assert "does not exist" in result.output
    assert MemoryStore().current_context_name() == "beta"


def test_bare_switch_requires_a_tty_without_a_mock_picker(isolated_store):
    invoke("init", "alpha")

    result = invoke("switch")

    assert result.exit_code == 1
    assert "requires a terminal" in result.output
    assert MemoryStore().current_context_name() == "alpha"


def test_bare_switch_reports_an_empty_store(isolated_store):
    result = invoke("switch")

    assert result.exit_code == 1
    assert "no contexts exist" in result.output


def test_explicit_switch_remains_noninteractive(
    isolated_store,
    monkeypatch,
):
    invoke("init", "alpha")
    invoke("init", "beta")

    def unexpected_picker(*args, **kwargs):
        raise AssertionError("explicit switch must not open the picker")

    monkeypatch.setattr(
        "memcommit.commands.switch.choose_context",
        unexpected_picker,
    )

    result = invoke("switch", "alpha")

    assert result.exit_code == 0
    assert MemoryStore().current_context_name() == "alpha"


def test_switch_dot_dot_moves_to_existing_lexical_namespace_parent(
    isolated_store,
):
    invoke("init", "organization/wiki")
    invoke("init", "organization/wiki/facilities")

    result = invoke("switch", "..")

    assert result.exit_code == 0
    assert "Switched to context 'organization/wiki'." in result.output
    assert MemoryStore().current_context_name() == "organization/wiki"


def test_switch_dot_dot_without_current_context_preserves_state(
    isolated_store,
):
    result = invoke("switch", "..")

    assert result.exit_code == 1
    assert "no current context is set" in result.output
    assert MemoryStore().current_context_name() is None


def test_switch_dot_dot_from_root_context_preserves_state(
    isolated_store,
):
    invoke("init", "campus")

    result = invoke("switch", "..")

    assert result.exit_code == 1
    assert "context 'campus' has no namespace parent" in result.output
    assert MemoryStore().current_context_name() == "campus"


def test_switch_dot_dot_requires_exact_parent_context(
    isolated_store,
):
    invoke("init", "organization/wiki")

    result = invoke("switch", "..")

    assert result.exit_code == 1
    assert "namespace parent context 'organization' does not exist" in result.output
    assert MemoryStore().current_context_name() == "organization/wiki"


def test_switch_dot_dot_does_not_infer_an_embedding_parent(
    isolated_store,
):
    invoke("init", "container")
    invoke("init", "topic/leaf")
    embedded = invoke("embed", "topic/leaf", "--into", "container")
    assert embedded.exit_code == 0
    invoke("switch", "topic/leaf")

    result = invoke("switch", "..")

    assert result.exit_code == 1
    assert "namespace parent context 'topic' does not exist" in result.output
    assert MemoryStore().current_context_name() == "topic/leaf"
